"""Reformats a .docx manuscript to a journal's rules and reports what is still missing."""
from pathlib import Path

from . import checks, reader, references, writer
from .model import ANSWERS, ASKED, Report

ROOT = Path(__file__).resolve().parent.parent


def run(manuscript_path, journal, out_root=ROOT / "output", answers=None, track_changes=False):
    """Read, check, fix and write. Returns the output folder and the report.
    `answers` maps (request, context) from model.ASKED to the author's text.
    With `track_changes`, the tool's edits show as tracked changes in Word."""
    ASKED.clear()
    ANSWERS.clear()
    ANSWERS.update({k: v.strip() for k, v in (answers or {}).items() if v.strip()})
    manuscript_path = Path(manuscript_path)
    ms = reader.read(manuscript_path)
    for p in [ms.title] + ms.paragraphs():
        p.original = list(p.runs)
    for s in ms.sections:
        s.original_title = s.title
    writer.TRACK_CHANGES = track_changes
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
    for (request, context), text in ANSWERS.items():
        if (request, context) in ASKED:
            what = request.strip("[]").split(": ", 1)[1]
            report.add(Report.SUPPLIED, what[0].upper() + what[1:], (f"{context}: " if context else "") + text)
    if track_changes:
        report.add(Report.MANUAL, "Tracked changes",
                   "The manuscript and title page show the tool's edits as tracked changes. Before submitting, "
                   "choose Review > Accept > Accept All Changes: deleted text stays inside the file until you do.")
    writer.report_file(report, journal, manuscript_path.name, files, out / "Compliance_Report.docx")
    return out, report
