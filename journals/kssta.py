"""Knee Surgery, Sports Traumatology, Arthroscopy. Values come from kssta-rules.txt."""

KSSTA = {
    "name": "Knee Surgery, Sports Traumatology, Arthroscopy",
    "short": "KSSTA",
    # Layout (spacing and margins are not specified by KSSTA: common defaults used)
    "font": "Times New Roman",
    "font_size": 10,
    "margins_inches": 0.98,            # 2.5 cm
    "first_page_number": 1,
    "new_page_before": [],
    "underline_becomes_italic": True,  # KSSTA uses italics for emphasis
    "headings": {"abstract": "Abstract", "introduction": "Introduction", "methods": "Methods",
                 "results": "Results", "discussion": "Discussion", "conclusions": "Conclusions",
                 "references": "References", "declarations": "Declarations"},
    # Abstract and title
    "abstract_max_words": 300,
    "abstract_headings": ["Purpose", "Methods", "Results", "Conclusions"],
    "abstract_abbreviations_allowed": False,
    "keywords": (4, 6),
    "title_abbreviations_allowed": True,
    "exact_p_values": False,
    # References
    "csl_style": "styles/kssta.csl",
    "citation_style": "brackets",      # [1, 4]
    "doi_required_from_year": 0,       # "always include if available"
    "books_need_isbn_and_pages": False,
    # Tables and figures (embedded in the text)
    "tables_in_separate_files": False,
    "figures_in_separate_files": False,
    "legends_section": False,
    "caption_label": "Fig. {n}",       # bold, no punctuation after the number
    "caption_ends_with_period": False,
    "flag_colour_words_in_captions": True,
    "flag_text_inside_figures": True,
    # Title page (ESSKA template) and Declarations
    "title_page_statements": {"funding": "Funding", "competing_interests": "Competing interests",
                              "ethics_approval": "Ethics approval", "consent_participate": "Consent to participate",
                              "consent_publish": "Consent to publish", "data_availability": "Data availability",
                              "author_contributions": "Author contributions"},
    "title_page_template": "ESSKA Title Page Template (esska.org/page/Journals_Title_Page_Template)",
    "orcid": True,
    "abbreviations_list": True,
    "declarations_in_manuscript": True,  # guide asks for both places; the manuscript copy is blinded
}
