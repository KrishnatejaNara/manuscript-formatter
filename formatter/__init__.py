"""Reformats a .docx manuscript to a journal's rules and reports what is still missing."""
from pathlib import Path

from . import checks, reader, references, writer
from .model import Report

ROOT = Path(__file__).resolve().parent.parent


def run(manuscript_path, journal, out_root=ROOT / "output"):
    """Read, check, fix and write. Returns the output folder."""
    manuscript_path = Path(manuscript_path)
    ms = reader.read(manuscript_path)
    report = Report()
    abstract_words = checks.word_count(ms.abstract)          # count before any notes are added

    checks.layout(ms, journal, report)
    checks.headings(ms, journal, report)
    references.process(ms, journal, report, ROOT, [a.name.split()[-1] for a in ms.authors])
    checks.abstract_and_title(ms, journal, report, abstract_words)
    checks.tables_and_figures(ms, journal, report)
    checks.blinding(ms, report)
    statements = checks.statements(ms, journal, report)

    out = Path(out_root) / f"{manuscript_path.stem}_{journal['short']}"
    out.mkdir(parents=True, exist_ok=True)
    writer.title_page(ms, journal, statements, out / "Title_Page.docx")
    writer.manuscript(ms, journal, statements, out / "Manuscript_Blinded.docx")
    files = ["Title_Page.docx", "Manuscript_Blinded.docx"] + writer.separate_files(ms, journal, out)
    writer.report_file(report, journal, manuscript_path.name, files, out / "Compliance_Report.docx")
    return out, report
