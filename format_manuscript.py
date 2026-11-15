"""Reformat a manuscript for a journal.

    .venv/bin/python format_manuscript.py example/fake-manuscript.docx --journal jses
"""
import argparse

from formatter import run
from journals import JOURNALS

parser = argparse.ArgumentParser(description="Reformat a .docx manuscript to a journal's rules.")
parser.add_argument("manuscript", help="the .docx file (it is never changed)")
parser.add_argument("--journal", required=True, choices=JOURNALS)
parser.add_argument("--track-changes", action="store_true", help="show the edits as tracked changes in Word")
args = parser.parse_args()

out, report = run(args.manuscript, JOURNALS[args.journal], track_changes=args.track_changes)
print(f"Done: {out}")
for status in report.ORDER:
    print(f"  {status}: {sum(1 for s, _, _ in report.items if s == status)}")
