from app.services.text_parser import ResumeParser, _clean_title_candidate, _merge_year_intervals


def test_merge_year_intervals_merges_overlap():
    merged = _merge_year_intervals([(2019, 2022), (2021, 2024), (2010, 2012)])
    assert merged == [(2010, 2012), (2019, 2024)]


def test_clean_title_candidate_strips_markdown_company_and_dates():
    raw = "## Director of Data & Analytics (Executive Leadership Team), FilterEasy (2023 - 2025)"
    assert _clean_title_candidate(raw) == "Director of Data & Analytics"


def test_resume_parser_excludes_education_years_from_experience():
    parser = ResumeParser()
    text = """
# Name
## Experience
## Director of Data, Company A (2021 - Present)
## Senior Manager, Company B (2018 - 2021)

## Education
MS Something (2002 - 2004)
BS Something Else (1998 - 2002)
"""
    parsed = parser.parse_text(text)
    # 2018 -> current year, should not include education years.
    assert parsed["experience_years"] is not None
    assert parsed["experience_years"] < 15


def test_resume_parser_extracts_clean_titles_and_current_title():
    parser = ResumeParser()
    text = """
## Experience
## Head of Data & Analytics, Acme Health (2023 - Present)
## Lead Data Scientist, Bark (2019 - 2022)
"""
    parsed = parser.parse_text(text)
    assert parsed["titles"][0] == "Head of Data & Analytics"
    assert "Lead Data Scientist" in parsed["titles"]
    assert parsed["current_title"] == "Head of Data & Analytics"


def test_resume_parser_normalizes_skills_from_taxonomy(monkeypatch):
    parser = ResumeParser()
    monkeypatch.setattr(
        "app.services.text_parser._load_taxonomy_map",
        lambda: {"machine learning": "Machine Learning", "sql": "SQL", "python": "Python"},
    )
    parsed = parser.parse_text("Built SQL and machine learning pipelines in Python")
    assert parsed["skills"] == ["Machine Learning", "SQL", "Python"]
