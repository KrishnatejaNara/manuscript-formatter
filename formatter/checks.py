"""Every check and fix applied to the manuscript before it is written out.

Fixes are mechanical only. Anything that needs the author's knowledge or
judgement gets a highlighted note and a report entry instead.
"""
import re
from dataclasses import replace

from .model import Figure, Para, Report, Run, Table, highlight, insert, note

ABBREVIATION = r"\b(?:\d[A-Z]-)?[A-Z]{2,}[A-Z0-9]*\b"
COMMON_ABBREVIATIONS = {"CT", "MRI", "SD", "BMI", "USA", "UK"}
IDENTIFYING_PHRASES = ["our group", "our institution", "our hospital", "our department", "our centre", "our center"]
COLOUR_WORDS = ["blue", "orange", "red", "green", "yellow", "purple", "grey", "gray"]


def word_count(paras):
    return sum(len(p.text.split()) for p in paras)


def layout(ms, j, report):
    o = ms.original
    report.add(Report.FIXED, "Page layout",
               f"Font: was {o['font']}, now {j['font']} {j['font_size']} pt.",
               "Spacing: " + ("was single, now double." if o["single_spaced"] else "double."),
               f"Margins: were {o['margins']}, now {j['margins_inches']:g} inch.",
               "Continuous line numbers and automatic page numbers (bottom right) added"
               + (f"; the manuscript starts at page {j['first_page_number']} because the title page is page 1." if j["first_page_number"] > 1 else "."),
               "Headings now use Word's real heading styles instead of plain bold text.")
    if j["new_page_before"]:
        report.add(Report.FIXED, "New page for each section",
                   "Page breaks before: " + ", ".join(j["headings"][k] for k in j["new_page_before"]) + ".")

    indented, underlined, struck = 0, [], []
    for p in ms.paragraphs() + [b for s in ms.statements.values() for b in s]:
        indented += p.space_indent
        runs = []
        for r in p.runs:
            if r.underline:
                underlined.append(r.text)
                r = replace(r, underline=False, italic=r.italic or j["underline_becomes_italic"])
            if r.strike:                       # keep the words; the author decides
                struck.append(r.text)
                runs += [replace(r, strike=False, highlight=True),
                         note(" [AUTHOR TO CHECK: this text was struck through. Delete it or keep it.]")]
                continue
            runs.append(r)
        p.runs = runs
    if indented:
        report.add(Report.FIXED, "Indents typed with spaces", f"Spaces removed from {indented} paragraph(s).")
    if underlined:
        report.add(Report.FIXED, "Underlined text", "Underline removed from: " + ", ".join(underlined)
                   + (" (now italic)." if j["underline_becomes_italic"] else "."))
    for text in struck:
        report.add(Report.TODO, "Struck-through text", f"'{text}' was kept and highlighted. Delete it if it was meant to go.")


def headings(ms, j, report):
    renamed = []
    for s in ms.sections:
        new = j["headings"].get(s.key, s.title)
        if new != s.title:
            renamed.append(f"'{s.title}' → '{new}'")
            s.title = new
    if renamed:
        report.add(Report.FIXED, "Section headings", "Renamed: " + ", ".join(renamed) + ". Subheadings kept as they were.")


def abstract_and_title(ms, j, report, abstract_words):
    if abstract_words > j["abstract_max_words"]:
        report.add(Report.TODO, "Abstract too long",
                   f"{abstract_words} words; the limit is {j['abstract_max_words']}. The tool does not shorten your text.")
    if not j["abstract_abbreviations_allowed"]:
        found = []
        for p in ms.abstract:
            found += highlight(p, ABBREVIATION)
        if found:
            report.add(Report.TODO, "Abbreviations in the abstract",
                       f"{j['short']} allows none. Highlighted: {', '.join(dict.fromkeys(found))}.")
    if j["abstract_headings"] and not re.match(r"\s*\w+:", ms.abstract[0].text):
        heads = " / ".join(j["abstract_headings"])
        ms.abstract.insert(0, Para([note(f"[AUTHOR TO SUPPLY: restructure the abstract under {heads}]")]))
        report.add(Report.TODO, "Abstract structure", f"{j['short']} needs exactly these headings: {heads}. "
                   "The tool does not split it, because that means deciding where each part begins.")
    low, high = j["keywords"]
    if not low <= len(ms.keywords) <= high:
        report.add(Report.TODO, "Keywords", f"{len(ms.keywords)} keywords; {j['short']} needs {low}-{high}.")
        ms.keyword_note = f" [AUTHOR TO SUPPLY: {low - len(ms.keywords)} more keyword(s)]" if len(ms.keywords) < low \
            else f" [AUTHOR TO CHECK: remove {len(ms.keywords) - high} keyword(s)]"
    if ms.level_of_evidence is None:
        report.add(Report.TODO, "Level of Evidence", "Missing. Add it at the end of the abstract (the tool never assigns it).")
    elif ms.original.get("level_of_evidence_in_title_block"):
        report.add(Report.FIXED, "Level of Evidence", "Moved from the title block to the end of the abstract.")
    if not j["title_abbreviations_allowed"]:
        found = [a for a in highlight(ms.title, ABBREVIATION) if a not in COMMON_ABBREVIATIONS]
        if found:
            report.add(Report.TODO, "Abbreviation in the title", f"{j['short']} asks you to avoid them. Highlighted: {', '.join(found)}.")
    if j["exact_p_values"]:
        threshold = r"\b[pP]\s*[<>]\s*0?\.(?!001\b)\d+"
        hits = sum(len(highlight(p, threshold)) for p in ms.paragraphs())
        for t in ms.blocks(Table):
            for row in t.rows:
                for cell in row:
                    if re.fullmatch(r"\s*<\s*0?\.(?!001\b)\d+\s*", cell.text):
                        cell.highlight, hits = True, hits + 1
        if hits:
            report.add(Report.TODO, "Exact P values", f"{hits} thresholds like 'p<0.05' highlighted; "
                       f"{j['short']} wants exact values, which only you have.")


def tables_and_figures(ms, j, report):
    for kind, word, items in (("Table", r"Tables?", ms.blocks(Table)), ("Figure", r"(?:Figures?|Fig\.)", ms.blocks(Figure))):
        order = []                                       # numbers in the order first mentioned
        for s in ms.sections:
            for p in s.blocks:
                if isinstance(p, Para):
                    order += [int(n) for n in re.findall(word + r"\s*(\d+)", p.text) if int(n) not in order]
        order += [i.number for i in items if i.number not in order]
        mapping = {old: new for new, old in enumerate(order, 1)}
        if any(o != n for o, n in mapping.items()):
            for p in [b for s in ms.sections for b in s.blocks if isinstance(b, Para)]:
                p.runs = [replace(r, text=re.sub(word + r"\s*(\d+)", lambda m: m[0][:-len(m[1])] + str(mapping[int(m[1])]), r.text))
                          for r in p.runs]
            for i in items:
                i.number = mapping[i.number]
            report.add(Report.FIXED, f"{kind} numbering", f"{kind}s renumbered in the order they are first mentioned: "
                       + "; ".join(f"{o} → {n}" for o, n in mapping.items() if o != n) + ".")

    for t in ms.blocks(Table):
        if t.had_lines_or_shading:
            report.add(Report.FIXED, "Table formatting", f"Table {t.number}: vertical lines and shading removed.")
        defined = " ".join(n.text for n in t.notes)
        used = re.findall(ABBREVIATION, " ".join(c.text for row in t.rows for c in row))
        missing = [a for a in dict.fromkeys(used) if a + "," not in defined and a not in COMMON_ABBREVIATIONS]
        if missing:
            t.notes.append(Para([note(f"[AUTHOR TO SUPPLY: table note defining {', '.join(missing)}]")]))
            report.add(Report.TODO, "Table notes", f"Table {t.number} does not define: {', '.join(missing)}.")

    for f in ms.blocks(Figure):
        body = re.sub(r"(?i)^\s*(figure|fig\.?)\s*\d+\s*[.:]?\s*", "", f.caption.text)
        if not j["caption_ends_with_period"]:
            body = body.rstrip(". ")
        f.caption = Para([Run(j["caption_label"].format(n=f.number), bold=True), Run(" " + body)])
        report.add(Report.FIXED, "Figure captions", f"Figure {f.number} caption now starts with '{j['caption_label'].format(n=f.number)}'"
                   + ("" if j["caption_ends_with_period"] else " and has no full stop at the end") + ".")
        if j["flag_colour_words_in_captions"]:
            found = highlight(f.caption, r"(?i)\b(" + "|".join(COLOUR_WORDS) + r")\b")
            if found:
                report.add(Report.TODO, "Colours in a caption", f"Figure {f.number} mentions {', '.join(found)}; "
                           "rephrase in case it is printed in black and white.")
        if (f.dpi or 0) < 300:
            report.add(Report.MANUAL, "Figure resolution", f"Figure {f.number} is saved at {f.dpi or 'unknown'} dpi; "
                       "at least 300 is needed. Export it again from the original software.")
        if j["flag_text_inside_figures"]:
            report.add(Report.MANUAL, "Text inside figures", f"{j['short']} does not allow a title inside the image. "
                       "The tool cannot read images: check each figure by eye.")
    if j["tables_in_separate_files"]:
        report.add(Report.FIXED, "Tables and figures", "Saved as separate files and removed from the manuscript; "
                   "their captions are in the 'Figure and Table Legends' section.")


def identifiers(ms):
    """Text that could reveal who the authors are."""
    found = []
    for a in ms.authors:
        parts = a.name.replace(".", " ").split()
        found += [a.name, parts[-1], ".".join(p[0] for p in parts) + "."]
    for _, aff in ms.affiliations:
        found += [x.strip() for x in aff.split(",") if re.search(r"(?i)universit|institute|hospital|cent(re|er)", x)]
    found += re.findall(r"[\w.+-]+@[\w.-]+", ms.corresponding)
    return list(dict.fromkeys(found))


def blinding(ms, report):
    report.add(Report.FIXED, "Blinding",
               "Author names, degrees, affiliations and corresponding author details moved to the title page.",
               *(["Acknowledgments moved to the title page."] if "acknowledgments" in ms.statements else []),
               *(["Competing interests statement moved to the title page."] if "competing_interests" in ms.statements else []),
               *(["Hidden file properties cleared (they contained " + "; ".join(f"{k}: {v}" for k, v in ms.original["properties"].items())
                  + ")."] if ms.original["properties"] else []))
    patterns = [r"(?<![\w.])" + re.escape(x) + r"(?![A-Za-z])" for x in identifiers(ms)]
    patterns += [r"(?i)\b" + p + r"(?![A-Za-z])" for p in IDENTIFYING_PHRASES]
    hits = []
    for p in [ms.title] + ms.paragraphs():
        for pattern in patterns:
            hits += highlight(p, pattern)
    if hits:
        report.add(Report.TODO, "Possible identifying text",
                   "Highlighted in the manuscript; confirm each one, then remove or black it out: " + ", ".join(dict.fromkeys(hits)) + ".")


def statements(ms, j, report):
    """Required statements: the author's own text where found, otherwise a note. Returns {key: runs}."""
    out = {k: [r for p in paras for r in p.runs] for k, paras in ms.statements.items()}
    methods = [b for s in ms.sections if s.key == "methods" for b in s.blocks if isinstance(b, Para)]

    for p in methods:
        m = re.search(r"(?i)[^.]*\b(ethic|IRB|institutional review board)[^.]*", p.text)
        if m:
            has_number = re.search(r"\d{3,}|\b(no\.|number)\s*\w+", m[0], re.I)
            has_date = re.search(r"\b(19|20)\d{2}\b", m[0])
            if not (has_number and has_date):
                insert(p, m.end(), [note(" [AUTHOR TO SUPPLY: ethics approval number and date]")])
                report.add(Report.TODO, "Ethics approval", "The statement in Methods has no approval number or date.")
            out["ethics_approval"] = [Run(m[0].strip() + ".")] + ([] if has_number and has_date
                                                                   else [note(" [AUTHOR TO SUPPLY: committee name, approval number and date]")])
            break
    else:
        report.add(Report.TODO, "Ethics approval", "No ethics approval statement found in Methods.")
    for p in methods:
        m = re.search(r"[^.]*informed consent[^.]*\.", p.text)
        if m:
            out["consent_participate"] = [Run(m[0].strip())]

    for key, label in j["title_page_statements"].items():
        if key not in out:
            out[key] = [note(f"[AUTHOR TO SUPPLY: {label.lower()} statement]")]
            report.add(Report.TODO, label, "No statement found; a highlighted note was added. The tool never writes it for you.")
    if j["orcid"]:
        report.add(Report.TODO, "ORCID iDs", "Add each author's ORCID iD on the title page, if they have one.")
    if j["abbreviations_list"]:
        report.add(Report.TODO, "List of abbreviations", f"{j['short']} wants one on the title page; a note was added.")
    if j["declarations_in_manuscript"]:
        report.add(Report.TODO, "Declarations section", "A blinded copy of the declarations is at the end of the manuscript. "
                   "Reword any highlighted names or initials there (e.g. 'One author is...').")
    report.add(Report.MANUAL, "Before submitting",
               f"Re-check the live {j['short']} author guidelines; the rules here were summarized in October 2026.",
               *([f"Paste the title page into the {j['title_page_template']}."] if j["title_page_template"] else []))
    return out
