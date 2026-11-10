"""References: read the list, find in-text citations, renumber and restyle.

Never looks anything up online and never invents DOIs, ISBNs or dates:
missing details become highlighted notes for the author.
"""
import html
import re
from dataclasses import dataclass, field, replace

from citeproc import Citation, CitationItem, CitationStylesBibliography, CitationStylesStyle
from citeproc import formatter as csl_formatter
from citeproc.source.json import CiteProcJSON

from .model import Para, Report, Run, note

YEAR = r"(?:19|20)\d{2}"


@dataclass
class Reference:
    number: int                 # number in the original list
    raw: str
    kind: str = "article"       # article / book / web / personal
    csl: dict = field(default_factory=dict)
    et_al: bool = False         # the original cut the author list short
    https_added: bool = False
    new_number: int = 0
    runs: list = field(default_factory=list)

    def label(self):
        a = (self.csl.get("author") or [{}])[0]
        return f"original ref {self.number} ({a.get('family') or a.get('literal')}) → now ref {self.new_number}"


# ---------------------------------------------------------------- reading the list

def parse(raw):
    number = int(re.match(r"\s*(\d+)", raw).group(1))
    text = re.sub(r"^\s*\d+[.)]\s*", "", raw)
    ref = Reference(number, raw, csl={"id": str(number), "type": "article-journal"})
    c = ref.csl

    doi = re.search(r"(?:https?://doi\.org/|\bdoi:\s*)(10\.\S+?)[.\s]*$", text, re.I)
    if doi:
        c["DOI"] = doi.group(1)
        text = text[:doi.start()].rstrip(" .") + "."

    if re.search(r"(?i)personal communication", text):
        ref.kind = "personal"
        c["author"] = authors(text.split(".")[0], ref)
        return ref

    url = re.search(r"(?i)(?:available (?:at|from):?\s*)?((?:https?://|www\.)\S+?)\.?$", text)
    if url:
        ref.kind, c["type"] = "web", "webpage"
        c["URL"] = url.group(1)
        if not c["URL"].startswith("http"):
            c["URL"], ref.https_added = "https://" + c["URL"], True
        parts = [p for p in re.split(r"\.\s+", text[:url.start()].strip(" .")) if p]
        c["author"], c["title"] = authors(parts[0], ref), parts[1]
        return ref

    apa = re.match(rf"(.+?)\s*\(({YEAR})\)\.\s*(.+?)\.\s+([^,]+),\s*(\d+)(?:\((\d+)\))?,\s*([\d-]+)", text)
    if apa:
        names = [{"family": f, "given": g.strip()} for f, g in re.findall(r"([A-Z][\w'-]+),\s*((?:[A-Z]\.\s*)+)", apa[1])]
        c.update(author=names, issued=year(apa[2]), title=apa[3], volume=apa[5], page=pages(apa[7]))
        c["container-title"] = apa[4]
        return ref

    head, rest = re.match(r"(.+?)\.\s+(.+)", text).groups() if ". " in text else ("", text)
    c["author"] = authors(head, ref)

    book = re.match(rf"(.+?)\.\s+(?:(\d+)\w\w\s+ed\.\s+)?([^.:;]+):\s*([^;]+);\s*({YEAR})", rest)
    if book:
        ref.kind, c["type"] = "book", "book"
        c.update(title=book[1], edition=book[2], publisher=book[4].strip(), issued=year(book[5]))
        c["publisher-place"] = book[3].strip()
        return ref

    art = re.match(rf"(.+?)\.\s+(.+?)\.?\s+({YEAR})\s*;?\s*(\d+)?\s*(?:\((\d+)\))?\s*:\s*([\d-]+)", rest)
    if not art:                                  # unknown format: keep the text, ask the author
        ref.kind, c["title"] = "other", rest
        return ref
    c.update(title=art[1], issued=year(art[3]), volume=art[4], issue=art[5], page=pages(art[6]))
    c["container-title"] = art[2]
    return ref


def authors(text, ref):
    """'Halvorsen TK, Mbeki LS, et al' -> CSL names. Organisations stay as written."""
    names = []
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        m = re.fullmatch(r"([A-Z][\w'-]*(?: [A-Z][\w'-]*)*?)\s+([A-Z]{1,4})", part)
        if re.fullmatch(r"(?i)et\.?\s*al\.?", part):
            ref.et_al = True
        elif m:
            names.append({"family": m[1], "given": " ".join(i + "." for i in m[2])})
        else:
            names.append({"literal": part})
    return names


def year(y):
    return {"date-parts": [[int(y)]]}


def pages(p):
    """211-9 -> 211-219"""
    if "-" not in p:
        return p
    a, b = p.split("-")
    return f"{a}-{a[:len(a) - len(b)] + b}"


# ---------------------------------------------------------------- citations in the text

def find_citations(para, refs):
    """Replace every citation in a paragraph with a citation Run. Returns what was found."""
    found, out = [], []
    for r in para.runs:
        if r.sup and re.fullmatch(r"[\d,\- ]+", r.text):                  # superscript 1,4
            out.append(Run("", cite=numbers(r.text)))
            found.append(("superscript", r.text))
            continue
        pos = 0
        pattern = rf"\s?\[([\d,\- ]+)\]|\s?\(([A-Z][\w'-]+)(?: et al\.?)?,? ({YEAR})\)"
        for m in re.finditer(pattern, r.text):
            if m[1]:
                nums = numbers(m[1])
            else:                                                          # (Nakamura et al., 2019)
                nums = [x.number for x in refs if x.csl.get("author") and x.csl["author"][0].get("family") == m[2]
                        and x.csl.get("issued") == year(m[3])]
                if not nums:
                    continue
            out.append(replace(r, text=r.text[pos:m.start()]))
            out.append(Run("", cite=nums))
            found.append(("brackets" if m[1] else "author-year", m.group(0).strip()))
            pos = m.end()
        out.append(replace(r, text=r.text[pos:]))
    para.runs = [r for r in out if r.text or r.cite]
    return found


def numbers(text):
    out = []
    for part in text.split(","):
        a, _, b = part.strip().partition("-")
        out += range(int(a), int(b or a) + 1)
    return out


def format_citation(nums, style):
    nums, parts = sorted(set(nums)), []
    for n in nums:                                    # 1,2,3,5 -> 1-3,5
        if parts and parts[-1][1] == n - 1:
            parts[-1][1] = n
        else:
            parts.append([n, n])
    sep = "," if style == "superscript" else ", "
    text = sep.join(f"{a}-{b}" if b - a >= 2 else sep.join(map(str, range(a, b + 1))) for a, b in parts)
    return text if style == "superscript" else f"[{text}]"


def render_citations(para, mapping, style):
    out = []
    for r in para.runs:
        if r.cite is None:
            out.append(r)
            continue
        known = [mapping[n] for n in r.cite if n in mapping]
        if known and style == "superscript":
            if out and out[-1].text.endswith(" "):     # superscript sits right after the word
                out[-1] = replace(out[-1], text=out[-1].text.rstrip())
            out.append(Run(format_citation(known, style), sup=True, highlight=r.highlight))
        elif known:
            out.append(Run(" " + format_citation(known, style), highlight=r.highlight))
        for n in [n for n in r.cite if n not in mapping]:
            out.append(note(f" [AUTHOR TO CHECK: citation {n} has no matching entry in the reference list]"))
    para.runs = out


# ---------------------------------------------------------------- the whole job

def process(ms, journal, report, root, author_surnames):
    refs = [parse(raw) for raw in ms.references]
    style = journal["citation_style"]

    # 1. Find citations everywhere
    cited, styles_found, abstract_cites = {}, set(), []
    for p in ms.paragraphs():
        for kind, text in find_citations(p, refs):
            styles_found.add(kind)
            if p in ms.abstract:
                abstract_cites.append(text)
        for r in p.runs:
            for n in r.cite or []:
                cited.setdefault(n, []).append(p)
    for p in ms.abstract:                                   # journals forbid citations in the abstract
        p.runs = [replace(r, highlight=True) if r.cite else r for r in p.runs]

    # 2. Personal communications belong in the text only
    personal = [r for r in refs if r.kind == "personal"]
    for ref in personal:
        for p in cited.get(ref.number, []):
            for i, r in enumerate(p.runs):
                if r.cite and ref.number in r.cite:
                    r.cite.remove(ref.number)
                    if r.cite:
                        continue
                    if "personal communication" in p.text:          # already mentioned: drop the number
                        p.runs[i - 1] = replace(p.runs[i - 1], text=p.runs[i - 1].text.rstrip())
                    else:                                           # otherwise say it in words
                        p.runs[i] = Run(f" ({ref.csl['author'][0].get('family')}, personal communication)")
    refs = [r for r in refs if r.kind != "personal"]

    # 3. The authors' own earlier work must be blinded
    own = [r for r in refs if len({a.get("family") for a in r.csl.get("author", [])} & set(author_surnames)) >= 2]
    for p in ms.paragraphs():
        p.runs = [replace(r, highlight=True) if r.cite and {o.number for o in own} & set(r.cite) else r for r in p.runs]

    # 4. Sort alphabetically and number with the journal's CSL style
    render_list(refs, root / journal["csl_style"], "et al." if style == "superscript" else "et al")
    mapping = {r.number: r.new_number for r in refs}
    for p in ms.paragraphs():
        render_citations(p, mapping, style)

    # 5. Notes for anything only the author can supply
    missing_doi, books = [], []
    for r in refs:
        y = r.csl.get("issued", {}).get("date-parts", [[0]])[0][0]
        if r.kind == "article" and "DOI" not in r.csl and y >= journal["doi_required_from_year"]:
            r.runs.append(note(" [AUTHOR TO SUPPLY: DOI]"))
            missing_doi.append(r)
        if r.kind == "book" and journal["books_need_isbn_and_pages"]:
            r.runs.append(note(" [AUTHOR TO SUPPLY: ISBN and relevant pages]"))
            books.append(r)
        if r.kind == "web":
            r.runs.append(note(" [AUTHOR TO SUPPLY: date last accessed]"))
        if r.kind == "other":
            r.runs.append(note(" [AUTHOR TO CHECK: the tool could not read this reference; format it by hand]"))
        if r.et_al:
            r.runs.append(note(" [AUTHOR TO CHECK: the original cut the author list short with 'et al.'; give all authors]"))
        if r in own:
            r.runs = [replace(x, highlight=True) for x in r.runs]
            r.runs.append(note(" [AUTHOR TO CHECK: the authors' own previous work; blind it as the journal requires]"))
        if r.number not in cited:
            r.runs = [replace(x, highlight=True) for x in r.runs]
            r.runs.append(note(" [AUTHOR TO CHECK: never cited in the text; cite it or delete it]"))
    ms.references = sorted(refs, key=lambda r: r.new_number)

    # 6. Report
    report.add(Report.FIXED, "Citations and reference list",
               f"Citation styles found: {', '.join(sorted(styles_found))}. All citations are now "
               + ("superscript numbers." if style == "superscript" else "numbers in [square brackets]."),
               "References sorted alphabetically, renumbered, and every in-text number updated: "
               + "; ".join(f"{r.number}→{r.new_number}" for r in ms.references) + ".",
               f"Every reference rewritten in {journal['short']} style (official CSL style, adjusted to the rules), "
               "so format, punctuation, author lists and DOIs are now consistent.")
    for ref in personal:
        report.add(Report.FIXED, "Personal communication",
                   f"Original ref {ref.number} removed from the list; the text still mentions it as a personal communication.")
    for n in sorted(set(cited) - {r.number for r in refs} - {r.number for r in personal}):
        report.add(Report.TODO, "Citation with no reference", f"Citation {n} is in the text but there is no reference {n}.")
    for r in refs:
        if r.number not in cited:
            report.add(Report.TODO, "Reference never cited", f"{r.label()}: cite it or delete it.")
        if r.et_al:
            report.add(Report.TODO, "Incomplete author list", f"{r.label()}: the original stopped at 'et al.'; give all authors.")
        if r in own:
            report.add(Report.TODO, "Citation of your own work",
                       f"{r.label()} shares authors with this manuscript. It and its citations are highlighted; blind them.")
        if r.kind == "web":
            report.add(Report.TODO, "Website reference", f"{r.label()}: add the date last accessed."
                       + (" 'https://' was added to the address; check it opens." if r.https_added else ""))
    if missing_doi:
        report.add(Report.TODO, "Missing DOIs", "Add DOIs for: " + "; ".join(r.label() for r in missing_doi)
                   + ". The tool never looks DOIs up or makes them up.")
    for r in books:
        report.add(Report.TODO, "Book reference", f"{r.label()}: add the ISBN and relevant pages.")
    if abstract_cites:
        report.add(Report.TODO, "Citation in the abstract",
                   f"The abstract cites {', '.join(abstract_cites)}. {journal['short']} does not allow references there.")


def render_list(refs, csl_path, et_al_text):
    items = []
    for r in refs:
        c = {k: v for k, v in r.csl.items() if v}
        if r.et_al:
            c["author"] = c["author"] + [{"literal": et_al_text}]
        items.append(c)
    bib = CitationStylesBibliography(CitationStylesStyle(str(csl_path), validate=False),
                                     CiteProcJSON(items), csl_formatter.html)
    for c in items:
        bib.register(Citation([CitationItem(c["id"])]))
    bib.sort()
    by_id = {r.csl["id"]: r for r in refs}
    for n, (item, text) in enumerate(zip(bib.items, bib.bibliography()), 1):
        ref = by_id[item.key]
        ref.new_number = n
        ref.runs = html_to_runs(re.sub(r"^\s*\d+\.\s*", "", str(text)).strip())


def html_to_runs(s):
    runs, italic = [], False
    for tok in re.split(r"(<[^>]+>)", s):
        if tok in ("<i>", "</i>"):
            italic = tok == "<i>"
        elif tok and not tok.startswith("<"):
            runs.append(Run(html.unescape(tok), italic=italic))
    return runs
