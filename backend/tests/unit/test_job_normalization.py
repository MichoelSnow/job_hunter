import pytest

from app.services.job_normalization import (
    extract_salary_from_text,
    html_to_text,
    infer_work_arrangement,
    normalize_location,
    sanitize_description_html,
)


class TestInferWorkArrangement:
    def test_remote_when_explicit_flag_true(self):
        value = infer_work_arrangement(
            title="Director of Data",
            location="New York, NY",
            description="",
            is_remote=True,
        )
        assert value == "remote"

    def test_hybrid_signal_from_location(self):
        value = infer_work_arrangement(
            title="VP Analytics",
            location="New York, NY (Hybrid)",
            description="",
            is_remote=None,
        )
        assert value == "hybrid"
    def test_in_office_signal_from_description(self):
        value = infer_work_arrangement(
            title="Head of Data",
            location="Manhattan",
            description="This is an in-office role with 4 days onsite.",
            is_remote=None,
        )
        assert value == "in_office"

    def test_unknown_when_no_signal(self):
        value = infer_work_arrangement(
            title="Director of Data",
            location="New York, NY",
            description="Strong SQL and Python required.",
            is_remote=False,
        )
        assert value == "unknown"

    def test_hybrid_when_office_required_part_of_week(self):
        value = infer_work_arrangement(
            title="Director of Data",
            location="New York, NY",
            description=(
                "This role will be based in our New York City office. "
                "You must be willing to work in the office 3 days per week."
            ),
            is_remote=None,
        )
        assert value == "hybrid"


class TestNormalizeLocation:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("New york city", "New York City, NY"),
            ("New York, NY", "New York City, NY"),
            ("New York", "New York City, NY"),
            ("NY", "New York City, NY"),
            ("New York City, New York", "New York City, NY"),
            ("New York, New York, United States", "New York City, NY"),
            ("New York Office", "New York City, NY"),
            ("SF Office", "San Francisco, CA"),
            ("Sf; Ny Hybrid Optional", "San Francisco, CA; New York City, NY"),
            ("Remote (SF or NY hybrid optional)", "San Francisco, CA; New York City, NY"),
            ("2 Locations", None),
            ("Remote, United States", "United States"),
            ("Hybrid - Palo Alto or San Francisco", "Palo Alto; San Francisco, CA"),
            ("New York, NY or Remote", "New York City, NY"),
            ("None, None", None),
        ],
    )
    def test_normalizes_city_level_locations(self, raw, expected):
        assert normalize_location(raw) == expected


class TestHtmlToText:
    def test_html_to_text_strips_tags(self):
        text = html_to_text("<p>Hybrid role</p><ul><li>Python</li></ul>")
        assert text == "Hybrid role Python"

    def test_html_to_text_unescapes_encoded_html_then_strips_tags(self):
        text = html_to_text("&lt;div&gt;Lead analytics &amp;amp; reporting&lt;/div&gt;")
        assert text == "Lead analytics & reporting"


class TestSanitizeDescriptionHtml:
    def test_preserves_basic_formatting_tags(self):
        html = sanitize_description_html(
            "&lt;div&gt;&lt;p&gt;<strong>Mission</strong> and <em>impact</em>&lt;/p&gt;"
            "&lt;ul&gt;&lt;li&gt;One&lt;/li&gt;&lt;li&gt;Two&lt;/li&gt;&lt;/ul&gt;&lt;/div&gt;"
        )
        assert "<strong>Mission</strong>" in html
        assert "<em>impact</em>" in html
        assert "<ul>" in html
        assert "<li>One</li>" in html

    def test_removes_unsafe_tags_and_links(self):
        html = sanitize_description_html(
            '<p>Hello</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a>'
            '<a href="https://example.com">good</a>'
        )
        assert "<script" not in html
        assert "javascript:" not in html
        assert '<a href="https://example.com"' in html


class TestExtractSalaryFromText:
    def test_extracts_yearly_range_with_hyphen(self):
        values = extract_salary_from_text("The base pay for this role is: $149,040 - $195,615 per year.")
        assert values == (149040, 195615, "year", "USD")

    def test_extracts_yearly_range_with_implied_base_salary_period(self):
        values = extract_salary_from_text(
            "The target base salary range for this position is $177,200 - $221,500 and is part "
            "of a competitive total rewards package including equity and benefits."
        )
        assert values == (177200, 221500, "year", "USD")

    def test_extracts_hourly_range_with_em_dash(self):
        values = extract_salary_from_text(
            "The estimated base pay range per hour for this role is:$17.67\u2014$24.34 USD"
        )
        assert values == (18, 24, "hour", "USD")

    def test_extracts_range_with_to_connector(self):
        values = extract_salary_from_text(
            "The target base salary for this position ranges from $170,000 to $200,000, in addition "
            "to a competitive equity and benefits package."
        )
        assert values == (170000, 200000, "year", "USD")

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (
                "Compensation Range: USD $88,540.00 - USD $141,687.00/Annually.",
                (88540, 141687, "year", "USD"),
            ),
            (
                "Benefits include a competitive salary range of $170,000 per year.",
                (170000, 170000, "year", "USD"),
            ),
            (
                "This position has a hiring range of USD $114,004.00 - USD $219,960.00 /Yr.",
                (114004, 219960, "year", "USD"),
            ),
            (
                "The salary for the Manager, Data and Analytic is $80,000.00 per year.",
                (80000, 80000, "year", "USD"),
            ),
            (
                "Total target base compensation will be between $190,000 and $260,000 per year.",
                (190000, 260000, "year", "USD"),
            ),
        ],
    )
    def test_extracts_salary_formats_from_historic_job_descriptions(self, text, expected):
        assert extract_salary_from_text(text) == expected
