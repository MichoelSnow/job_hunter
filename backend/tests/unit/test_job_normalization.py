from app.services.job_normalization import (
    extract_salary_from_text,
    html_to_text,
    infer_work_arrangement,
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
