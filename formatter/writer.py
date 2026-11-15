"""Writes fresh Word files. Building new files (instead of editing the original)
means hidden leftovers such as the author's name in File > Properties never carry over."""
import io
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Inches, Pt, RGBColor

from .checks import identifiers
from .model import Figure, Para, Report, Run, Table, highlight, note

COLOURS = {Report.TODO: "F8CBAD", Report.MANUAL: "FFE699", Report.FIXED: "C6EFCE", Report.SUPPLIED: "BDD7EE"}


def new_document(j, line_numbers=True, first_page=1):
    d = Document()
    for prop in ("author", "last_modified_by", "title", "comments", "keywords", "subject"):
        setattr(d.core_properties, prop, "")
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        style = d.styles[name]
        style.font.name, style.font.size, style.font.color.rgb = j["font"], Pt(j["font_size"]), RGBColor(0, 0, 0)
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):   # theme fonts would win
            fonts.attrib.pop(qn(attr), None)
        fonts.set(qn("w:eastAsia"), j["font"])
        style.paragraph_format.line_spacing = 2.0
        style.paragraph_format.space_after = Pt(0)
        if name != "Normal":
            style.font.bold, style.font.italic = True, name == "Heading 2"
    for border in d.styles["Title"].element.findall(".//" + qn("w:pBdr")):   # default Title has a blue rule
        border.getparent().remove(border)

    section = d.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Inches(j["margins_inches"])
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    field = xml("w:fldSimple", {"w:instr": "PAGE"})                   # automatic page number
    run, text = xml("w:r", {}), xml("w:t", {})
    text.text = "1"
    run.append(text)
    field.append(run)
    footer._p.append(field)
    # Word expects these section settings just before <w:cols>
    cols = section._sectPr.find(qn("w:cols"))
    if line_numbers:
        cols.addprevious(xml("w:lnNumType", {"w:countBy": "1", "w:restart": "continuous"}))
    cols.addprevious(xml("w:pgNumType", {"w:start": str(first_page)}))
    return d


def xml(tag, attrs):
    el = OxmlElement(tag)
    for k, v in attrs.items():
        el.set(qn(k), v)
    return el


def add(d, runs, style=None, new_page=False):
    p = d.add_paragraph(style=style)
    p.paragraph_format.page_break_before = new_page
    for r in runs:
        if r.text:
            run = p.add_run(r.text)
            run.bold, run.italic, run.font.superscript = r.bold or None, r.italic or None, r.sup or None
            if r.highlight:
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return p


def add_table(d, t):
    add(d, table_caption(t))
    table = d.add_table(rows=len(t.rows), cols=len(t.rows[0]))
    borders = xml("w:tblBorders", {})            # horizontal rules only: no vertical lines, no shading
    for edge in ("top", "bottom", "insideH"):
        borders.append(xml(f"w:{edge}", {"w:val": "single" if edge != "insideH" else "nil", "w:sz": "8"}))
    table._tbl.tblPr.find(qn("w:tblLook")).addprevious(borders)
    for i, row in enumerate(t.rows):
        for k, cell in enumerate(row):
            p = table.cell(i, k).paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            add_runs(p, [Run(cell.text, bold=i == 0, highlight=cell.highlight)])
    for n in t.notes:
        add(d, n.runs)


def add_runs(p, runs):
    for r in runs:
        run = p.add_run(r.text)
        run.bold = r.bold or None
        if r.highlight:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def table_caption(t):
    title = re.sub(r"(?i)^\s*table\s*\d+\s*[.:]?\s*", "", t.caption.text) if t.caption else ""
    return [Run(f"Table {t.number}.", bold=True), Run(" " + title)]


# ---------------------------------------------------------------- the output files

def title_page(ms, j, statements, path):
    d = new_document(j, line_numbers=False)
    letters = j["short"] == "JSES"                 # JSES links authors to affiliations with a, b, c
    mark = lambda m: re.sub(r"\d+", lambda n: "abcdefghij"[int(n[0]) - 1], m) if letters else m
    for p in ms.notice:
        add(d, p.runs)
    add(d, ms.title.runs, style="Title")
    if ms.running_title:
        add(d, ms.running_title.runs)
    authors = []
    for i, a in enumerate(ms.authors):
        authors += [Run((", " if i else "") + ", ".join([a.name] + a.degrees)), Run(",".join(map(mark, a.marks)), sup=True)]
    add(d, authors)
    for m, text in ms.affiliations:
        add(d, [Run(mark(m), sup=True), Run(text)])
    add(d, [Run("*Corresponding author: ", bold=True), Run(ms.corresponding)])
    if j["orcid"]:
        add(d, [Run("ORCID iDs", bold=True)])
        for a in ms.authors:
            add(d, [Run(a.name + ": "), note("[AUTHOR TO SUPPLY: ORCID iD, if available]", a.name)])
    if j["abbreviations_list"]:
        add(d, [Run("Abbreviations", bold=True)])
        add(d, [note("[AUTHOR TO SUPPLY: list of abbreviations used in the manuscript]")])
    if "acknowledgments" in statements:
        add(d, [Run("Acknowledgments", bold=True)])
        add(d, statements["acknowledgments"])
    for key, label in j["title_page_statements"].items():
        add(d, [Run(label, bold=True)])
        add(d, statements[key])
    d.save(path)


def manuscript(ms, j, statements, path):
    d = new_document(j, first_page=j["first_page_number"])
    h, new_page = j["headings"], set(j["new_page_before"])
    for p in ms.notice:
        add(d, p.runs)
    add(d, ms.title.runs, style="Title")
    add(d, [Run(h["abstract"])], style="Heading 1", new_page="abstract" in new_page)
    for p in ms.abstract:
        add(d, p.runs)
    add(d, [Run("Level of Evidence: ", bold=True),
            Run(ms.level_of_evidence) if ms.level_of_evidence else note("[AUTHOR TO SUPPLY: Level of Evidence]")])
    add(d, [Run("Keywords: ", bold=True), Run("; ".join(ms.keywords))] + ([note(ms.keyword_note)] if ms.keyword_note else []))

    for s in ms.sections:
        add(d, [Run(s.title)], style="Heading 1", new_page=s.key in new_page)
        waiting = sorted([b for b in s.blocks if not isinstance(b, Para)], key=lambda b: (isinstance(b, Figure), b.number))
        for b in [b for b in s.blocks if isinstance(b, Para)]:
            add(d, [Run(r.text) for r in b.runs] if b.heading else b.runs, style="Heading 2" if b.heading else None)
            for item in list(waiting):          # tables/figures go after the paragraph that first mentions them
                word = "Table" if isinstance(item, Table) else "Fig"
                if re.search(rf"{word}\w*\.?\s*{item.number}\b", b.text):
                    waiting.remove(item)
                    embed(d, item, j)
        for item in waiting:
            embed(d, item, j)

    if j["declarations_in_manuscript"]:
        add(d, [Run(h["declarations"])], style="Heading 1")
        names = identifiers(ms)
        for key, label in j["title_page_statements"].items():
            p = Para([Run(label + ": ", bold=True)] + statements[key])
            for x in names:                     # the blinded copy must not name anyone
                highlight(p, r"(?<![\w.])" + re.escape(x) + r"(?![A-Za-z])")
            add(d, p.runs)

    add(d, [Run(h["references"])], style="Heading 1", new_page="references" in new_page)
    for r in ms.references:
        add(d, [Run(f"{r.new_number}. ")] + r.runs)

    if j["legends_section"]:
        add(d, [Run(h["legends"])], style="Heading 1", new_page="legends" in new_page)
        for f in sorted(ms.blocks(Figure), key=lambda f: f.number):
            add(d, f.caption.runs)
        for t in sorted(ms.blocks(Table), key=lambda t: t.number):
            add(d, table_caption(t))
    d.save(path)


def embed(d, item, j):
    if isinstance(item, Table) and not j["tables_in_separate_files"]:
        add_table(d, item)
    elif isinstance(item, Figure) and not j["figures_in_separate_files"]:
        d.add_paragraph().add_run().add_picture(io.BytesIO(item.image), width=Emu(item.width_emu))
        add(d, item.caption.runs)


def separate_files(ms, j, out_dir):
    files = []
    if j["tables_in_separate_files"]:
        for t in sorted(ms.blocks(Table), key=lambda t: t.number):
            d = new_document(j, line_numbers=False)
            add_table(d, t)
            d.save(out_dir / f"Table_{t.number}.docx")
            files.append(f"Table_{t.number}.docx")
    if j["figures_in_separate_files"]:
        for f in ms.blocks(Figure):
            (out_dir / f"Figure_{f.number}.{f.ext}").write_bytes(f.image)
            files.append(f"Figure_{f.number}.{f.ext}")
    return files


def report_file(report, j, manuscript_name, files, path):
    d = Document()
    d.core_properties.author = ""
    d.add_heading(f"Compliance report: {j['name']} ({j['short']})", 0)
    d.add_paragraph(f"Manuscript: {manuscript_name}")
    d.add_paragraph("Files produced: " + ", ".join(files) + ".")
    summary = d.add_table(rows=0, cols=2)
    summary.style = "Table Grid"
    for status in Report.ORDER:
        n = sum(1 for s, _, _ in report.items if s == status)
        cells = summary.add_row().cells
        cells[0].text, cells[1].text = status, str(n)
        cells[0]._tc.get_or_add_tcPr().append(xml("w:shd", {"w:val": "clear", "w:fill": COLOURS[status]}))
    for status in Report.ORDER:
        d.add_heading(status, 1)
        for s, title, details in report.items:
            if s == status:
                d.add_paragraph().add_run(title).bold = True
                for line in details:
                    d.add_paragraph(line, style="List Bullet")
    d.save(path)
