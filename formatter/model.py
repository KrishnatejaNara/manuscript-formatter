"""Plain data describing a manuscript, plus the compliance report."""
import re
from dataclasses import dataclass, field, replace
from typing import List, Optional


@dataclass
class Run:
    """A stretch of text with one set of formatting."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    sup: bool = False
    highlight: bool = False
    cite: Optional[List[int]] = None   # set when this run is an in-text citation (original ref numbers)
    ins: bool = False                  # added by the tool: shown as a tracked insertion
    deleted: bool = False              # removed by the tool: shown as a tracked deletion


ASKED = []     # every (request, context) the last run needed from the author, for the app's form
ANSWERS = {}   # (request, context) -> the author's own text, typed into the app


def note(text, context=""):
    """A highlighted message for the author, or the author's answer to it if they gave one.
    `context` tells apart requests with the same text (e.g. which reference needs a DOI)."""
    m = re.search(r"\[AUTHOR TO SUPPLY: [^\]]*\]", text)
    if m:
        key = (m[0], context)
        if key not in ASKED:
            ASKED.append(key)
        if ANSWERS.get(key):
            return Run(text[:m.start()] + ANSWERS[key], ins=True)
    return Run(text, bold=True, highlight=True, ins=True)


@dataclass
class Para:
    runs: List[Run]
    heading: bool = False         # True for a subheading inside a section
    space_indent: bool = False    # the original was indented with typed spaces
    original: Optional[list] = None   # the runs as read, to show changes against

    @property
    def text(self):
        return "".join(r.text for r in self.runs)


@dataclass
class Table:
    number: int
    caption: Optional[Para]
    rows: List[List[Run]]   # one Run per cell
    notes: List[Para] = field(default_factory=list)
    had_lines_or_shading: bool = False


@dataclass
class Figure:
    number: int
    caption: Optional[Para]
    image: bytes
    ext: str
    width_emu: int
    dpi: Optional[int]


@dataclass
class Section:
    key: Optional[str]      # e.g. "methods"; None if not recognised
    title: str
    blocks: list = field(default_factory=list)   # Para / Table / Figure
    original_title: str = ""


@dataclass
class Author:
    name: str
    degrees: List[str]
    marks: List[str]


@dataclass
class Manuscript:
    notice: List[Para] = field(default_factory=list)     # e.g. the FICTIONAL banner
    title: Optional[Para] = None
    running_title: Optional[Para] = None
    authors: List[Author] = field(default_factory=list)
    affiliations: List[tuple] = field(default_factory=list)   # (mark, text)
    corresponding: str = ""
    level_of_evidence: Optional[str] = None
    abstract: List[Para] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    keyword_note: str = ""                                # e.g. "[AUTHOR TO SUPPLY: 1 more keyword]"
    sections: List[Section] = field(default_factory=list)
    statements: dict = field(default_factory=dict)       # e.g. {"acknowledgments": [Para]}
    references: list = field(default_factory=list)       # raw strings, later Reference objects
    original: dict = field(default_factory=dict)         # facts about the input file

    def paragraphs(self):
        """Every text paragraph, in reading order, including captions and table notes."""
        out = list(self.abstract)
        for s in self.sections:
            for b in s.blocks:
                if isinstance(b, Para):
                    out.append(b)
                else:
                    out += [b.caption] if b.caption else []
                    out += getattr(b, "notes", [])
        return out

    def blocks(self, kind):
        return [b for s in self.sections for b in s.blocks if isinstance(b, kind)]


# ---------------------------------------------------------------- editing runs

def split_at(runs, positions):
    """Split runs so every character position given becomes a run boundary."""
    out, start = [], 0
    for r in runs:
        end = start + len(r.text)
        cuts = sorted({p - start for p in positions if start < p < end})
        prev = 0
        for c in cuts + [len(r.text)]:
            out.append(replace(r, text=r.text[prev:c]))
            prev = c
        start = end
    return out


def highlight(para, pattern, flags=0):
    """Highlight every regex match in a paragraph. Returns the matched strings."""
    matches = [m for m in re.finditer(pattern, para.text, flags) if m.group(0)]
    spans = [(m.start(), m.end()) for m in matches]
    if spans:
        para.runs = split_at(para.runs, [p for s in spans for p in s])
        pos = 0
        for r in para.runs:
            if any(a <= pos < b for a, b in spans) and r.text:
                r.highlight = True
            pos += len(r.text)
    return [m.group(0) for m in matches]


def insert(para, position, new_runs):
    runs = split_at(para.runs, [position])
    pos = 0
    for i, r in enumerate(runs):
        if pos >= position:
            para.runs = runs[:i] + new_runs + runs[i:]
            return
        pos += len(r.text)
    para.runs = runs + new_runs


# ---------------------------------------------------------------- report

class Report:
    TODO = "Needs your input"
    MANUAL = "Check by hand"
    FIXED = "Fixed automatically"
    SUPPLIED = "Filled in by you"
    ORDER = [TODO, MANUAL, SUPPLIED, FIXED]

    def __init__(self):
        self.items = []   # (status, title, [details])

    def add(self, status, title, *details):
        for s, t, existing in self.items:          # group repeated entries under one title
            if (s, t) == (status, title):
                existing.extend(details)
                return
        self.items.append((status, title, list(details)))
