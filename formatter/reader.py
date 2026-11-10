"""Reads a .docx manuscript and works out what each part is."""
import re
import struct
from collections import Counter

import docx
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph

from .model import Author, Figure, Manuscript, Para, Run, Section, Table

SECTION_NAMES = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background"],
    "methods": ["methods", "materials and methods", "patients and methods"],
    "results": ["results"],
    "discussion": ["discussion"],
    "conclusions": ["conclusion", "conclusions"],
    "acknowledgments": ["acknowledgments", "acknowledgements"],
    "competing_interests": ["conflict of interest", "conflicts of interest", "competing interests", "disclosures"],
    "funding": ["funding"],
    "references": ["references"],
}
HEADING_LOOKUP = {name: key for key, names in SECTION_NAMES.items() for name in names}
DEGREES = {"MD", "PhD", "MSc", "BSc", "MBBS", "FRCSC", "FRCS", "MPH", "MS", "DO", "MBA", "BA", "MA", "PT", "DPT"}
STATEMENT_SECTIONS = {"acknowledgments", "competing_interests", "funding"}


def read(path):
    d = docx.Document(path)
    ms = Manuscript(original=describe(d))
    body = [Paragraph(el, d) if el.tag == qn("w:p") else DocxTable(el, d)
            for el in d.element.body.iterchildren() if el.tag in (qn("w:p"), qn("w:tbl"))]

    # Everything before the "Abstract" heading is the title block
    start = next(i for i, b in enumerate(body) if is_heading(b) and section_key(b.text) == "abstract")
    read_title_block(ms, [b for b in body[:start] if isinstance(b, Paragraph)])

    section, tables, figures, i = None, 0, 0, start
    while i < len(body):
        b = body[i]
        nxt = body[i + 1] if i + 1 < len(body) else None
        if isinstance(b, DocxTable):                       # a table without a caption
            tables += 1
            section.blocks.append(read_table(b, tables, None))
        elif is_heading(b):
            key = section_key(b.text)
            if key or not is_subheading(b):
                section = Section(key, b.text.strip())
                ms.sections.append(section)
            else:
                section.blocks.append(Para(read_runs(b), heading=True))
        elif b._p.xpath(".//a:blip"):                      # an image; the caption follows it
            figures += 1
            caption = None
            if isinstance(nxt, Paragraph) and re.match(r"(?i)fig(ure|\.)?\s*\d", nxt.text.strip()):
                caption, i = para(nxt), i + 1
            section.blocks.append(read_figure(d, b, figures, caption))
        elif re.match(r"(?i)table\s+\d+", b.text.strip()) and isinstance(nxt, DocxTable):
            tables += 1
            table = read_table(nxt, tables, para(b))
            i += 1
            after = body[i + 1] if i + 1 < len(body) else None
            if isinstance(after, Paragraph) and looks_like_table_note(after.text):
                table.notes.append(para(after))
                i += 1
            section.blocks.append(table)
        elif b.text.strip():
            section.blocks.append(para(b))
        i += 1

    # Pull out the parts that are kept separately
    abstract = ms.sections.pop(0)
    for p in abstract.blocks:
        if re.match(r"(?i)key\s*words?\s*:", p.text):
            ms.keywords = [k.strip(" .") for k in re.split(r"[;,]", p.text.split(":", 1)[1]) if k.strip(" .")]
        elif re.match(r"(?i)level of evidence", p.text):
            ms.level_of_evidence = p.text.split(":", 1)[-1].strip()
        else:
            ms.abstract.append(p)
    for s in list(ms.sections):
        if s.key == "references":
            ms.references = [p.text.strip() for p in s.blocks]
            ms.sections.remove(s)
        elif s.key in STATEMENT_SECTIONS:
            ms.statements[s.key] = s.blocks
            ms.sections.remove(s)
    return ms


def read_title_block(ms, paragraphs):
    for p in paragraphs:
        text, runs = p.text.strip(), read_runs(p)
        low = text.lower()
        if not text:
            continue
        if low.startswith("fictional test manuscript"):
            ms.notice.append(Para(runs))
        elif low.startswith("running title"):
            ms.running_title = Para(runs)
        elif low.startswith("level of evidence"):
            ms.level_of_evidence = text.split(":", 1)[-1].strip()
            ms.original["level_of_evidence_in_title_block"] = True
        elif "corresponding author" in low:
            ms.corresponding = re.sub(r"(?i)^\*?\s*corresponding author\s*:?\s*", "", text)
        elif runs[0].sup and not DEGREES & set(re.split(r"[,\s]+", text)):
            ms.affiliations.append((runs[0].text.strip(), "".join(r.text for r in runs[1:]).strip()))
        elif DEGREES & set(re.split(r"[,\s]+", text)):
            ms.authors = parse_authors(runs)
        elif ms.title is None:
            ms.title = Para([Run(r.text, sup=r.sup) for r in runs])


def parse_authors(runs):
    """'Emeka J. Okafor, MD' + superscript '1' + ', Danielle R. Brennan, ...'"""
    authors = []
    for r in runs:
        if r.sup:
            authors[-1].marks += [m for m in re.split(r"[,\s]+", r.text) if m]
            continue
        for token in [t.strip() for t in r.text.split(",")]:
            if token in DEGREES:
                authors[-1].degrees.append(token)
            elif token:
                authors.append(Author(token, [], []))
    return authors


def read_table(t, number, caption):
    rows = [[Run(" ".join(p.text for p in cell.paragraphs)) for cell in row.cells] for row in t.rows]
    xml = t._tbl.xml
    lines = re.search(r'<w:insideV\b[^>]*w:val="(?!nil|none)', xml)
    shading = re.search(r'<w:shd\b[^>]*w:fill="(?!auto|FFFFFF)', xml)
    return Table(number, caption, rows, had_lines_or_shading=bool(lines or shading))


def looks_like_table_note(text):
    return bool(re.search(r"\b[A-Z]{2,}, [a-z]", text) or re.match(r"(?i)(note|values|\*)", text.strip()))


def read_figure(d, p, number, caption):
    part = d.part.related_parts[p._p.xpath(".//a:blip")[0].get(qn("r:embed"))]
    width = int(p._p.xpath(".//wp:extent")[0].get("cx"))
    return Figure(number, caption, part.blob, part.partname.split(".")[-1], width, png_dpi(part.blob))


def png_dpi(blob):
    """Resolution stored in a PNG file (None for other formats)."""
    i = blob.find(b"pHYs")
    if blob[:4] != b"\x89PNG" or i < 0:
        return None
    per_metre, _, unit = struct.unpack(">IIB", blob[i + 4:i + 13])
    return round(per_metre * 0.0254) if unit == 1 else None


def para(p):
    runs = read_runs(p)
    spaces = bool(runs) and runs[0].text.startswith("  ")   # indent typed with spaces
    if spaces:
        runs[0].text = runs[0].text.lstrip(" ")
    return Para(runs, space_indent=spaces)


def read_runs(p):
    return [Run(r.text, bold=bool(r.bold), italic=bool(r.italic), underline=bool(r.underline),
                strike=bool(r.font.strike), sup=bool(r.font.superscript))
            for r in p.runs if r.text]


def is_heading(b):
    """Short, all-bold paragraphs are headings (the test file has no heading styles)."""
    if not isinstance(b, Paragraph) or not b.text.strip():
        return False
    if b.style is not None and b.style.name.startswith("Heading"):
        return True
    text = b.text.strip()
    runs = [r for r in b.runs if r.text.strip()]
    return (len(text.split()) <= 10 and not text.endswith((".", ":")) and not re.match(r"(?i)(table|fig)", text)
            and all(r.bold for r in runs))


def is_subheading(p):
    runs = [r for r in p.runs if r.text.strip()]
    return all(r.italic for r in runs) or (p.style is not None and p.style.name == "Heading 2")


def section_key(text):
    return HEADING_LOOKUP.get(re.sub(r"[^a-z ]", "", text.lower()).strip())


def describe(d):
    """Facts about the original file, for the report."""
    s = d.sections[0]
    sizes = Counter(r.font.size.pt for p in d.paragraphs for r in p.runs if r.font.size for _ in r.text)
    name = next((r.font.name for p in d.paragraphs for r in p.runs if r.font.name), "Calibri")
    xml = d.element.xml
    props = d.core_properties
    return {
        "font": f"{name} {sizes.most_common(1)[0][0]:g} pt",   # the size most of the text uses
        "margins": f"{s.left_margin.inches:g} inch",
        "line_numbers": "<w:lnNumType" in xml,
        "single_spaced": not re.search(r'w:line="(36\d|4[0-9]{2})"', xml),
        "properties": {k: v for k, v in [("author", props.author), ("last modified by", props.last_modified_by),
                                         ("title", props.title)] if v},
    }
