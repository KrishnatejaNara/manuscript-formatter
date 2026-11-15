# Manuscript Formatting Tool

Reformats a research manuscript (`.docx`) to a journal's author guidelines.
It produces the files the journal wants, plus a compliance report that lists
what was fixed and what still needs the author.

Supported journals: **JSES** (Journal of Shoulder and Elbow Surgery) and
**KSSTA** (Knee Surgery, Sports Traumatology, Arthroscopy).

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python format_manuscript.py example/fake-manuscript.docx --journal jses
```

Output goes to `output/<manuscript>_<JOURNAL>/`:

- `Compliance_Report.docx`: what was fixed, what needs you, what to check by hand
- `Title_Page.docx`: a separate title page with authors, affiliations and statements
- `Manuscript_Blinded.docx`: the anonymized manuscript
- JSES only: `Table_N.docx` and `Figure_N.png` as separate files

## Desktop app

```bash
.venv/bin/python app.py
```

Choose the manuscript, the journal and where to save. The **Fill in** tab lists
everything only the author can supply (DOIs, ethics approval, funding, ORCID iDs, …);
type answers into any boxes you like, then press **Format manuscript**. Your text goes
exactly where the highlighted note would have been; empty boxes stay as notes. The
**Changes** tab then lists what was fixed, filled in and still needs you.

Tkinter comes with the python.org installer for macOS. With Homebrew Python, run
`brew install python-tk` first.

To make a double-clickable `Manuscript Formatter.app` (in `dist/`):

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --windowed --name "Manuscript Formatter" --add-data styles:styles --collect-data citeproc --collect-all docx app.py
```

## How it works

```
format_manuscript.py        command-line entry point
app.py                      desktop app (tkinter)
formatter/
  reader.py                 .docx -> a simple model (title block, abstract, sections, tables, figures, references)
  references.py             parse references, find citations, sort/renumber, render with a CSL style
  checks.py                 layout, headings, abstract, tables/figures, blinding, required statements
  writer.py                 build fresh .docx files and the report
  model.py                  data classes and the report
journals/                   one settings file per journal, next to the rules it encodes
styles/                     CSL citation styles (official styles, adjusted to each journal's rules)
example/                    a fictional manuscript with planted errors, and its answer key
```

Some design choices:

- **Fix the mechanical, flag the rest.** Fonts, spacing, heading names, citation
  numbering and reference punctuation are fixed automatically. Anything only the
  author knows gets a yellow `[AUTHOR TO SUPPLY: …]` note, never invented text.
  That covers funding, ethics approval numbers, DOIs, keywords and Level of Evidence.
- **Blinding is highlighted, not deleted.** Author names, initials, the
  institution and phrases like "our group" are highlighted for the author to
  confirm. Hidden file properties (e.g. the author's name) are cleared.
- **Standard citation styles.** References are converted to structured data and
  rendered with [CSL](https://citationstyles.org) via `citeproc-py`, so a list sorts
  and renumbers correctly and every in-text number is updated to match.
- **Fresh output files.** Outputs are built from scratch rather than edited, so
  nothing hidden carries over from the original. The input file is never changed.
- **Adding a journal** means adding one settings file in `journals/` and,
  if needed, a CSL style.

## Example

`example/fake-manuscript.docx` is a fictional paper with 56 deliberate
errors, listed in `example/fake-manuscript-answer-key.txt`. The tool fixes or
flags all of them for both journals.

## Limits

- It cannot see inside images (figure resolution is reported; text inside a
  figure must be checked by eye).
- It recognises common reference formats (Vancouver, APA, books, websites);
  anything else is flagged to format by hand.
- Journal rules were summarized in October 2026. Always check the journal's
  current guidelines.
