"""Journal of Shoulder and Elbow Surgery. Values come from jses-rules.txt."""

JSES = {
    "name": "Journal of Shoulder and Elbow Surgery",
    "short": "JSES",
    # Layout
    "font": "Times New Roman",
    "font_size": 12,
    "margins_inches": 1.0,
    "first_page_number": 2,            # the title page counts as page 1
    "new_page_before": ["abstract", "introduction", "methods", "results", "discussion",
                        "conclusions", "references", "legends"],
    "underline_becomes_italic": False,
    "headings": {"abstract": "Abstract", "introduction": "Introduction", "methods": "Materials and Methods",
                 "results": "Results", "discussion": "Discussion", "conclusions": "Conclusions",
                 "references": "References", "legends": "Figure and Table Legends"},
    # Abstract and title
    "abstract_max_words": 400,
    "abstract_headings": None,         # not specified by JSES
    "abstract_abbreviations_allowed": True,
    "keywords": (6, 8),
    "title_abbreviations_allowed": False,
    "exact_p_values": True,
    # References
    "csl_style": "styles/jses.csl",
    "citation_style": "superscript",   # 1,4  (no brackets)
    "doi_required_from_year": 2002,
    "books_need_isbn_and_pages": True,
    # Tables and figures
    "tables_in_separate_files": True,
    "figures_in_separate_files": True,
    "legends_section": True,
    "caption_label": "Figure {n}.",
    "caption_ends_with_period": True,
    "flag_colour_words_in_captions": False,
    "flag_text_inside_figures": False,
    # Title page and statements
    "title_page_statements": {"competing_interests": "Declaration of competing interests", "funding": "Funding"},
    "title_page_template": None,
    "orcid": False,
    "abbreviations_list": False,
    "declarations_in_manuscript": False,
}
