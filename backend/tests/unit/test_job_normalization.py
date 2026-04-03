from app.services.job_normalization import html_to_text, infer_work_arrangement


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
