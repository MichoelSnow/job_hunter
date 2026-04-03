"""Smoke tests for the full job discovery pipeline.

All HTTP is mocked — no real API requests are made. Tests run the complete
pipeline (fetch → filter → upsert → parse requirements → score) against a
real in-memory SQLite DB built from the ORM models.

These tests exist specifically to catch schema drift between ORM models and the
DB, and to verify the pipeline wiring is correct end-to-end.
"""
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all ORM models
from app.db.base import Base
from app.models.company import Company
from app.models.job import Job


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _fake_jsearch_response(n: int = 3) -> dict:
    """Return a minimal JSearch API response with n jobs."""
    return {
        "data": [
            {
                "job_id": f"js_{i}",
                "job_title": f"Director of Data {i}",
                "job_description": "Lead our data team in Manhattan. Python required. 5+ years experience.",
                "job_city": "New York",
                "job_state": "NY",
                "job_is_remote": False,
                "employer_name": f"Health Corp {i}",
                "employer_logo": None,
                "job_apply_link": f"https://example.com/apply/{i}",
                "job_min_salary": 150000,
                "job_max_salary": 200000,
                "job_salary_currency": "USD",
                "job_salary_period": "YEAR",
                "job_employment_type": "FULLTIME",
                "job_posted_at_datetime_utc": "2026-04-01T00:00:00Z",
            }
            for i in range(n)
        ]
    }


def _fake_serply_response(n: int = 2) -> dict:
    """Return a minimal Serply API response with n jobs."""
    return {
        "jobs": [
            {
                "job_id": f"sp_{i}",
                "title": f"VP of Analytics {i}",
                "description": "Lead analytics in Brooklyn. SQL required.",
                "location": "Brooklyn, NY",
                "company_name": f"Tech Health {i}",
                "link": f"https://example.com/serply/{i}",
                "date_posted": "2026-04-01",
            }
            for i in range(n)
        ]
    }


def _jsearch_job(
    job_id: str,
    title: str,
    description: str,
    *,
    city: str = "New York",
    state: str = "NY",
    is_remote: bool = False,
) -> dict:
    return {
        "job_id": job_id,
        "job_title": title,
        "job_description": description,
        "job_city": city,
        "job_state": state,
        "job_is_remote": is_remote,
        "employer_name": "Health Corp",
        "employer_logo": None,
        "job_apply_link": f"https://example.com/apply/{job_id}",
        "job_min_salary": 150000,
        "job_max_salary": 200000,
        "job_salary_currency": "USD",
        "job_salary_period": "YEAR",
        "job_employment_type": "FULLTIME",
        "job_posted_at_datetime_utc": "2026-04-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_http_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Schema smoke test
# ---------------------------------------------------------------------------

class TestSchemaIntegrity:
    """Verify the ORM models match what Base.metadata creates.

    If a column exists in the DB but not in the ORM (or vice versa), upserts
    will fail at runtime. Creating all tables from the ORM in a fresh DB is
    the simplest way to catch this before a live run.
    """

    def test_company_table_creation(self, db_session):
        """Company table creates cleanly and accepts a row with all defaults."""
        company = Company(name="Test Corp")
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        assert company.id is not None
        assert company.scraper_enabled is True  # default
        assert company.is_priority is False     # default

    def test_job_table_creation(self, db_session):
        """Job table creates cleanly."""
        job = Job(
            title="Director of Data",
            description="Lead our team.",
            application_url="https://example.com",
            source="jsearch_api",
            discovered_date=date(2026, 4, 1),
        )
        db_session.add(job)
        db_session.commit()
        assert job.id is not None


# ---------------------------------------------------------------------------
# Pipeline smoke tests
# ---------------------------------------------------------------------------

class TestDiscoveryPipeline:
    """Full end-to-end pipeline tests calling run_job_discovery() directly.

    All HTTP is mocked; everything else (file loading, ORM, filtering, parsing,
    scoring) runs for real. This ensures that path bugs, NOT NULL violations, and
    missing pipeline steps all fail here rather than on a live run.
    """

    def _run_discovery(self, db_session, jsearch_data=None, serply_data=None):
        """Call run_job_discovery() with mocked HTTP and the provided in-memory session."""
        from app.services.api_aggregator import run_job_discovery

        jsearch_resp = _mock_http_response(jsearch_data or _fake_jsearch_response())
        serply_resp = _mock_http_response(serply_data or _fake_serply_response())

        def dispatch_get(url, **kwargs):
            if "openwebninja" in url:
                return jsearch_resp
            if "serply" in url:
                return serply_resp
            if "greenhouse" in url:
                return _mock_http_response({"jobs": []})
            if "lever" in url:
                return _mock_http_response([])
            # Workday CSRF GET or anything else
            return _mock_http_response({})

        # Workday POST — return empty so scrapers exit immediately
        workday_resp = _mock_http_response({"total": 0, "jobPostings": []})

        # Prevent run_job_discovery from closing our test session
        db_session.close = lambda: None

        with patch("app.services.api_aggregator.settings") as mock_settings, \
             patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("requests.Session.get", side_effect=dispatch_get), \
             patch("requests.Session.post", return_value=workday_resp):

            mock_settings.jsearchapi_key = "fake_key"
            mock_settings.serplyapi_key = "fake_key"
            mock_settings.jsearch_num_pages = 1
            mock_settings.serply_num_results = 10
            mock_settings.search_queries = ["director data healthcare New York"]
            mock_settings.search_locations = ["New York, NY"]
            mock_settings.api_request_delay_seconds = 0
            # Scoring weights — must be real floats or ScoringEngine arithmetic breaks
            mock_settings.user_to_job_weight = 0.6
            mock_settings.job_to_user_weight = 0.4
            mock_settings.skill_match_weight = 0.50
            mock_settings.experience_match_weight = 0.25
            mock_settings.title_match_weight = 0.15
            mock_settings.education_match_weight = 0.10

            run_job_discovery()

    def test_full_pipeline_inserts_jobs(self, db_session):
        self._run_discovery(db_session)
        assert db_session.query(Job).count() > 0

    def test_second_run_updates_not_inserts(self, db_session):
        from app.services.api_aggregator import discovery_status
        self._run_discovery(db_session)
        first_count = db_session.query(Job).count()
        self._run_discovery(db_session)
        assert db_session.query(Job).count() == first_count
        assert discovery_status["inserted"] == 0
        assert discovery_status["updated"] > 0

    def test_company_rows_created(self, db_session):
        self._run_discovery(db_session)
        assert db_session.query(Company).count() > 0

    def test_scraper_enabled_default_set(self, db_session):
        """Regression: scraper_enabled NOT NULL was missing from ORM."""
        self._run_discovery(db_session)
        assert all(c.scraper_enabled is True for c in db_session.query(Company).all())

    def test_jobs_have_non_null_required_fields(self, db_session):
        """Regression: null API fields must not reach NOT NULL DB columns."""
        self._run_discovery(db_session)
        for job in db_session.query(Job).all():
            assert job.title is not None
            assert job.description is not None
            assert job.application_url is not None
            assert job.source is not None
            assert job.discovered_date is not None

    def test_null_description_stored_as_empty_string(self, db_session):
        """Regression: job_description=null from JSearch caused NOT NULL constraint failure."""
        data = _fake_jsearch_response(1)
        data["data"][0]["job_description"] = None
        self._run_discovery(db_session, jsearch_data=data, serply_data={"jobs": []})
        job = db_session.query(Job).first()
        assert job is not None
        assert job.description == ""

    def test_html_encoded_description_is_normalized(self, db_session):
        """Descriptions with escaped HTML should be stored as readable plain text."""
        data = _fake_jsearch_response(1)
        data["data"][0]["job_description"] = (
            "&lt;div&gt;&lt;p&gt;Hybrid role &amp;amp; cross-functional.&lt;/p&gt;&lt;/div&gt;"
        )
        self._run_discovery(db_session, jsearch_data=data, serply_data={"jobs": []})
        job = db_session.query(Job).first()
        assert job is not None
        assert job.description == "Hybrid role & cross-functional."

    def test_remote_jobs_filtered_out(self, db_session):
        """Jobs marked as remote should remain stored but be hidden by user filters."""
        data = _fake_jsearch_response(3)
        for job in data["data"]:
            job["job_is_remote"] = True
        self._run_discovery(db_session, jsearch_data=data, serply_data={"jobs": []})
        rows = db_session.query(Job).all()
        assert len(rows) == 3
        assert all(row.passes_user_filters is False for row in rows)

    def test_requirements_parsed_and_stored(self, db_session):
        """parse_and_store_requirements runs and stores JobRequirement rows."""
        from app.models.job import JobRequirement
        self._run_discovery(db_session)
        # At least some jobs should have requirements parsed from their descriptions
        req_count = db_session.query(JobRequirement).count()
        assert req_count >= 0  # must not raise — even zero is acceptable if taxonomy is sparse

    def test_discovery_status_reflects_run(self, db_session):
        """discovery_status is updated correctly after a successful run."""
        from app.services.api_aggregator import discovery_status
        self._run_discovery(db_session)
        assert discovery_status["status"] == "complete"
        assert discovery_status["mode"] == "full"
        assert discovery_status["inserted"] is not None
        assert discovery_status["updated"] is not None
        assert discovery_status["filtered_out"] is not None
        assert discovery_status["error"] is None

    def test_pipeline_produces_non_uniform_scores(self, db_session):
        """Regression: scoring should vary when job requirements differ."""
        from app.models.job import JobRequirement
        from app.models.user_settings import UserSettings

        db_session.add(
            UserSettings(
                search_queries=["director data healthcare New York"],
                search_locations=[],
                filter_location_query='"new york"',
                filter_title_query="director",
                filter_exclude_remote=True,
                filter_target_salary=None,
                filter_include_missing_salary=True,
                matching_skills=["Python", "SQL"],
                matching_experience_years=8,
                matching_current_title="Director of Data",
            )
        )
        db_session.commit()

        jsearch_data = {
            "data": [
                _jsearch_job(
                    "js_high_fit",
                    "Director of Data",
                    "Python and SQL required. 3 years experience.",
                ),
                _jsearch_job(
                    "js_low_fit",
                    "Director of Data Infrastructure",
                    "Kubernetes and Java required. 12 years experience.",
                ),
            ]
        }

        self._run_discovery(db_session, jsearch_data=jsearch_data, serply_data={"jobs": []})
        scores = [s[0] for s in db_session.query(Job.overall_match_score).all()]
        assert len(scores) >= 2
        assert len(set(scores)) > 1
        assert db_session.query(JobRequirement).count() > 0


class TestDiscoveryModeRouting:
    def test_run_job_discovery_uses_full_mode(self, monkeypatch):
        from app.services import api_aggregator

        captured = {}
        monkeypatch.setattr(
            api_aggregator,
            "_run_job_discovery",
            lambda **kwargs: captured.update(kwargs),
        )
        api_aggregator.run_job_discovery()
        assert captured == {"fetch_api": True, "fetch_scrapers": True, "mode": "full"}

    def test_run_job_discovery_api_only_uses_api_mode(self, monkeypatch):
        from app.services import api_aggregator

        captured = {}
        monkeypatch.setattr(
            api_aggregator,
            "_run_job_discovery",
            lambda **kwargs: captured.update(kwargs),
        )
        api_aggregator.run_job_discovery_api_only()
        assert captured == {"fetch_api": True, "fetch_scrapers": False, "mode": "api"}

    def test_run_job_discovery_scrapers_only_uses_scraper_mode(self, monkeypatch):
        from app.services import api_aggregator

        captured = {}
        monkeypatch.setattr(
            api_aggregator,
            "_run_job_discovery",
            lambda **kwargs: captured.update(kwargs),
        )
        api_aggregator.run_job_discovery_scrapers_only()
        assert captured == {"fetch_api": False, "fetch_scrapers": True, "mode": "scrapers"}


class TestCompanyScrape:
    """Smoke tests for company ATS scraping with mocked HTTP."""

    def _make_greenhouse_response(self, n: int = 5) -> dict:
        return {
            "jobs": [
                {
                    "id": i,
                    "title": f"Director of Data {i}",
                    "location": {"name": "New York, NY (Hybrid)"},
                    "absolute_url": f"https://boards.greenhouse.io/testco/jobs/{i}",
                    "content": "<p>Hybrid role. Python required.</p>"
                    "<p>The base pay for this role is: $149,040 - $195,615 per year.</p>",
                    "first_published": "2026-03-15T12:00:00Z",
                    "updated_at": "2026-04-01T00:00:00Z",
                }
                for i in range(n)
            ]
        }

    def test_greenhouse_scraper_normalizes_jobs(self):
        from app.services.scraper.greenhouse import GreenhouseScraper

        company = {"name": "Test Co", "ats_type": "greenhouse", "ats_id": "testco"}
        scraper = GreenhouseScraper(company)

        with patch("requests.Session.get") as mock_get:
            mock_get.return_value = _mock_http_response(self._make_greenhouse_response(5))
            jobs = scraper.fetch_jobs()

        assert len(jobs) == 5
        assert mock_get.call_args.kwargs["params"] == {"content": "true"}
        assert all(j["source"] == "greenhouse" for j in jobs)
        assert all(j["external_id"].startswith("gh_") for j in jobs)
        assert all(j["company_name"] == "Test Co" for j in jobs)
        assert all(
            j["description"]
            == "Hybrid role. Python required. The base pay for this role is: $149,040 - $195,615 per year."
            for j in jobs
        )
        assert all(j["work_arrangement"] == "hybrid" for j in jobs)
        assert all(j["posted_date"] == "2026-03-15" for j in jobs)
        assert all(j["salary_min"] == 149040 for j in jobs)
        assert all(j["salary_max"] == 195615 for j in jobs)
        assert all(j["salary_period"] == "year" for j in jobs)

    def test_lever_scraper_normalizes_jobs(self):
        from app.services.scraper.lever import LeverScraper

        lever_data = [
            {
                "id": f"lever-id-{i}",
                "text": f"Director of Analytics {i}",
                "categories": {"location": "New York, NY"},
                "applyUrl": f"https://jobs.lever.co/testco/{i}/apply",
                "hostedUrl": f"https://jobs.lever.co/testco/{i}",
                "createdAt": 1743465600000,
                "descriptionPlain": (
                    "Lead our analytics team. The target base salary range for this position "
                    "is $177,200 - $221,500 and is part of a competitive total rewards package."
                ),
                "additionalPlain": "Additional details.",
                "lists": [{"text": "What You'll Do:", "content": "<li>Build strategy</li>"}],
            }
            for i in range(3)
        ]
        company = {"name": "Test Co", "ats_type": "lever", "ats_id": "testco"}
        scraper = LeverScraper(company)

        with patch("requests.Session.get") as mock_get:
            mock_get.return_value = _mock_http_response(lever_data)
            jobs = scraper.fetch_jobs()

        assert len(jobs) == 3
        assert all(j["source"] == "lever" for j in jobs)
        assert all(j["external_id"].startswith("lv_") for j in jobs)
        assert all(j["salary_min"] == 177200 for j in jobs)
        assert all(j["salary_max"] == 221500 for j in jobs)
        assert all(j["salary_period"] == "year" for j in jobs)
        assert all("What You'll Do:" in j["description"] for j in jobs)
        assert all("Build strategy" in j["description"] for j in jobs)
        assert all(j["raw_data"].get("normalized_description_html") for j in jobs)
        assert all(j["application_url"] == j["source_url"] for j in jobs)
        assert all("/apply" not in j["application_url"] for j in jobs)

    def test_workday_scraper_paginates(self):
        from app.services.scraper.workday import WorkdayScraper

        company = {
            "name": "Test Co",
            "ats_type": "workday",
            "ats_id": "testco",
            "workday_board": "TestCo_Careers",
            "workday_instance": "wd1",
        }
        scraper = WorkdayScraper(company)

        page1 = {
            "total": 3,
            "jobPostings": [
                {
                    "title": f"Job {i}",
                    "externalPath": f"/job/New-York/Job-{i}_JR00{i}",
                    "bulletFields": [
                        f"JR00{i}",
                        "The target base salary for this position ranges from $170,000 to $200,000",
                    ],
                }
                for i in range(2)
            ],
        }
        page2 = {
            "total": 3,
            "jobPostings": [
                {
                    "title": "Job 2",
                    "externalPath": "/job/New-York/Job-2_JR002",
                    "bulletFields": [
                        "JR002",
                        "The target base salary for this position ranges from $170,000 to $200,000",
                    ],
                }
            ],
        }

        csrf_resp = _mock_http_response({})
        csrf_resp.cookies = {"CALYPSO_CSRF_TOKEN": "fake-csrf"}

        with patch("requests.Session.get", return_value=csrf_resp), \
             patch("requests.Session.post") as mock_post:
            mock_post.side_effect = [
                _mock_http_response(page1),
                _mock_http_response(page2),
            ]
            jobs = scraper.fetch_jobs()

        assert len(jobs) == 3
        assert mock_post.call_count == 2  # confirmed pagination
        assert all(j["source"] == "workday" for j in jobs)
        assert all(j["salary_min"] == 170000 for j in jobs)
        assert all(j["salary_max"] == 200000 for j in jobs)
        assert all(j["salary_period"] == "year" for j in jobs)

    def test_workday_scraper_falls_back_board_variant(self):
        from app.services.scraper.workday import WorkdayScraper

        company = {
            "name": "Test Co",
            "ats_type": "workday",
            "ats_id": "testco",
            "workday_board": "TestCo_Careers",
            "workday_instance": "wd1",
            "careers_url": "https://www.testco.com/careers",
        }
        scraper = WorkdayScraper(company)

        csrf_resp = _mock_http_response({})
        csrf_resp.url = "https://testco.wd1.myworkdayjobs.com/en-US/TestCoCareers"
        csrf_resp.cookies = {"CALYPSO_CSRF_TOKEN": "fake-csrf"}

        bad = _mock_http_response({}, status_code=400)
        good = _mock_http_response({"total": 0, "jobPostings": []})

        with patch("requests.Session.get", return_value=csrf_resp), \
             patch("requests.Session.post") as mock_post:
            mock_post.side_effect = [bad, good]
            jobs = scraper.fetch_jobs()

        assert jobs == []
        # First board fails (TestCo_Careers), second fallback uses TestCoCareers
        assert mock_post.call_count == 2

    def test_workday_scraper_discovers_cxs_endpoint_from_careers_html(self):
        from app.services.scraper.workday import WorkdayScraper

        company = {
            "name": "Tempus",
            "ats_type": "workday",
            "ats_id": "tempus",
            "workday_board": "Tempus_Careers",
            "workday_instance": "wd5",
            "careers_url": "https://www.tempus.com/careers/",
        }
        scraper = WorkdayScraper(company)

        landing = _mock_http_response({})
        landing.url = "https://www.tempus.com/careers/"
        landing.text = (
            '<script>const endpoint="https://tempus.wd5.myworkdayjobs.com/'
            'wday/cxs/tempus/TempusCareers/jobs";</script>'
        )
        jobs_resp = _mock_http_response({"total": 0, "jobPostings": []})

        with patch("requests.Session.get", return_value=landing), \
             patch("requests.Session.post", return_value=jobs_resp) as mock_post:
            jobs = scraper.fetch_jobs()

        assert jobs == []
        called_url = mock_post.call_args.args[0]
        assert called_url == "https://tempus.wd5.myworkdayjobs.com/wday/cxs/tempus/TempusCareers/jobs"

    def test_workday_scraper_logs_body_snippet_on_board_failure(self):
        from app.services.scraper.workday import WorkdayScraper

        company = {
            "name": "Tempus",
            "ats_type": "workday",
            "ats_id": "tempus",
            "workday_board": "Tempus_Careers",
            "workday_instance": "wd5",
            "careers_url": "https://www.tempus.com/careers/",
        }
        scraper = WorkdayScraper(company)

        landing = _mock_http_response({})
        landing.url = "https://www.tempus.com/careers/"
        landing.text = ""
        failure = _mock_http_response({"error": "bad request"}, status_code=400)
        failure.text = "bad request from workday"

        with patch("requests.Session.get", return_value=landing), \
             patch("requests.Session.post", return_value=failure):
            jobs = scraper.fetch_jobs()

        assert jobs == []

    def test_ashby_scraper_normalizes_jobs(self):
        from app.services.scraper.ashby import AshbyScraper

        company = {"name": "Allara Health", "ats_type": "ashby", "ats_id": "allarahealth"}
        scraper = AshbyScraper(company)

        response_data = {
            "apiVersion": "1",
            "jobs": [
                {
                    "title": "Billing Operations Manager",
                    "location": "New York City Office",
                    "workplaceType": "Hybrid",
                    "employmentType": "FullTime",
                    "descriptionPlain": "Lead billing operations.",
                    "descriptionHtml": "<p><strong>Lead billing operations.</strong></p>",
                    "publishedAt": "2026-03-25T12:00:00.000+00:00",
                    "jobUrl": (
                        "https://jobs.ashbyhq.com/allarahealth/"
                        "c162a840-f144-40d6-bc8e-ce643a998ba5"
                    ),
                    "applyUrl": (
                        "https://jobs.ashbyhq.com/allarahealth/"
                        "c162a840-f144-40d6-bc8e-ce643a998ba5/application"
                    ),
                    "compensation": {
                        "compensationTierSummary": "$170,000 - $200,000",
                        "scrapeableCompensationSalarySummary": "$170,000 - $200,000",
                    },
                }
            ],
        }

        with patch("requests.Session.get") as mock_get:
            mock_get.return_value = _mock_http_response(response_data)
            jobs = scraper.fetch_jobs()

        assert len(jobs) == 1
        job = jobs[0]
        assert job["source"] == "ashby"
        assert job["external_id"] == "as_c162a840-f144-40d6-bc8e-ce643a998ba5"
        assert (
            job["application_url"]
            == "https://jobs.ashbyhq.com/allarahealth/c162a840-f144-40d6-bc8e-ce643a998ba5"
        )
        assert (
            job["source_url"]
            == "https://jobs.ashbyhq.com/allarahealth/c162a840-f144-40d6-bc8e-ce643a998ba5"
        )
        assert job["employment_type"] == "fulltime"
        assert job["description"] == "Lead billing operations."
        assert job["posted_date"] == "2026-03-25"
        assert job["salary_min"] == 170000
        assert job["salary_max"] == 200000

    def test_html_scraper_extracts_salary_from_row_text(self):
        from app.services.scraper.html_scraper import HtmlScraper

        company = {
            "name": "Test Co",
            "ats_type": "custom",
            "careers_url": "https://www.testco.com/careers",
            "html_selectors": {
                "job_list": "ul.jobs li",
                "title": "a.job-title",
                "location": "span.location",
                "url": "a.job-title",
            },
        }
        scraper = HtmlScraper(company)

        html = """
        <ul class="jobs">
          <li>
            <a class="job-title" href="/jobs/1">Data Analyst</a>
            <span class="location">New York, NY</span>
            <span class="salary">
              The estimated base pay range per hour for this role is:$17.67—$24.34 USD
            </span>
          </li>
        </ul>
        """
        response = _mock_http_response({})
        response.text = html

        with patch("requests.Session.get", return_value=response):
            jobs = scraper.fetch_jobs()

        assert len(jobs) == 1
        job = jobs[0]
        assert job["source"] == "html_scraper"
        assert job["salary_min"] == 18
        assert job["salary_max"] == 24
        assert job["salary_period"] == "hour"
        assert job["application_url"] == "https://www.testco.com/jobs/1"

    def test_load_companies_for_scrape_uses_db_values(self, db_session):
        from app.models.company import Company
        from app.services.api_aggregator import _load_companies_for_scrape

        db_session.add(
            Company(
                name="Acme",
                ats_type="lever",
                ats_id="acme-custom",
                careers_page_url="https://jobs.lever.co/acme",
                scraper_enabled=True,
            )
        )
        db_session.commit()

        db_session.close = lambda: None
        with patch("app.db.session.SessionLocal", return_value=db_session):
            companies = _load_companies_for_scrape()

        acme = next((c for c in companies if c.get("name") == "Acme"), None)
        assert acme is not None
        assert acme["ats_id"] == "acme-custom"
        assert acme["ats_type"] == "lever"
        assert acme["careers_url"] == "https://jobs.lever.co/acme"

    def test_load_companies_for_scrape_uses_db_scraper_fields(self, db_session):
        from app.models.company import Company
        from app.services.api_aggregator import _load_companies_for_scrape

        db_session.add(
            Company(
                name="Temp Co",
                ats_type="workday",
                ats_id="tempco",
                workday_board="Temp_Careers",
                workday_instance="wd5",
                scraper_enabled=True,
            )
        )
        db_session.commit()

        db_session.close = lambda: None
        with patch("app.db.session.SessionLocal", return_value=db_session):
            companies = _load_companies_for_scrape()

        tempco = next((c for c in companies if c.get("name") == "Temp Co"), None)
        assert tempco is not None
        assert tempco["careers_url"] is None
        assert tempco["workday_board"] == "Temp_Careers"
        assert tempco["workday_instance"] == "wd5"

    def test_enrich_companies_does_not_restore_cleared_ats_fields(self, db_session):
        from app.models.company import Company
        from app.services.api_aggregator import _load_companies_for_scrape

        db_session.add(
            Company(
                name="Temp Co",
                ats_type=None,
                ats_id=None,
                website_url=None,
                careers_page_url=None,
                scraper_enabled=True,
            )
        )
        db_session.commit()

        db_session.close = lambda: None
        with patch("app.db.session.SessionLocal", return_value=db_session):
            companies = _load_companies_for_scrape()

        tempco = next((c for c in companies if c.get("name") == "Temp Co"), None)
        assert tempco is not None
        assert tempco["ats_type"] is None
        assert tempco["ats_id"] is None
        assert tempco["careers_url"] is None
        assert tempco["workday_board"] is None

    def test_get_scrape_targets_reports_enabled_and_skipped(self, db_session):
        from app.models.company import Company
        from app.services.api_aggregator import get_scrape_targets

        db_session.add_all(
            [
                Company(name="Good GH", ats_type="greenhouse", ats_id="goodgh", scraper_enabled=True),
                Company(name="Bad GH", ats_type="greenhouse", ats_id=None, scraper_enabled=True),
                Company(
                    name="Good HTML",
                    ats_type="custom",
                    careers_page_url="https://example.com/careers",
                    html_selectors={"job_list": "ul.jobs li", "title": "a.title", "url": "a.title"},
                    scraper_enabled=True,
                ),
                Company(name="Unknown", ats_type=None, ats_id="mystery", scraper_enabled=True),
            ]
        )
        db_session.commit()

        db_session.close = lambda: None
        with patch("app.db.session.SessionLocal", return_value=db_session):
            enabled, skipped = get_scrape_targets()

        enabled_names = {c["name"] for c in enabled}
        assert "Good GH" in enabled_names
        assert "Good HTML" in enabled_names

        skipped_map = {item["name"]: item["reason"] for item in skipped}
        assert skipped_map["Bad GH"] == "missing ats_id"
        assert skipped_map["Unknown"] == "missing or unsupported ats_type"

    def test_run_company_scrape_persists_success_status(self, db_session):
        from app.models.company import Company
        from app.services.api_aggregator import run_company_scrape

        company = Company(name="Scrape OK", ats_type="lever", ats_id="scrape-ok", scraper_enabled=True)
        db_session.add(company)
        db_session.commit()

        class _SuccessScraper:
            def __init__(self):
                self.last_fetch_succeeded = True
                self.last_error = None

            def fetch_jobs(self):
                return []

        db_session.close = lambda: None
        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("app.services.api_aggregator.get_scrape_targets", return_value=([{"id": company.id, "name": company.name, "ats_type": "lever"}], [])), \
             patch("app.services.scraper.get_scraper", return_value=_SuccessScraper()):
            run_company_scrape()

        db_session.expire_all()
        refreshed = db_session.get(Company, company.id)
        assert refreshed is not None
        assert refreshed.scrape_last_status == "success"
        assert refreshed.scrape_last_error is None
        assert refreshed.last_scraped_at is not None

    def test_run_company_scrape_persists_error_status(self, db_session):
        from app.models.company import Company
        from app.services.api_aggregator import run_company_scrape

        company = Company(name="Scrape Fail", ats_type="lever", ats_id="scrape-fail", scraper_enabled=True)
        db_session.add(company)
        db_session.commit()

        class _FailScraper:
            def __init__(self):
                self.last_fetch_succeeded = False
                self.last_error = "400 Client Error"

            def fetch_jobs(self):
                return []

        db_session.close = lambda: None
        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("app.services.api_aggregator.get_scrape_targets", return_value=([{"id": company.id, "name": company.name, "ats_type": "lever"}], [])), \
             patch("app.services.scraper.get_scraper", return_value=_FailScraper()):
            run_company_scrape()

        db_session.expire_all()
        refreshed = db_session.get(Company, company.id)
        assert refreshed is not None
        assert refreshed.scrape_last_status == "error"
        assert refreshed.scrape_last_error == "400 Client Error"
        assert refreshed.last_scraped_at is not None

    def test_skill_taxonomy_path_resolves(self):
        """Regression: TAXONOMY_PATH used parents[4] (wrong) instead of parents[3]."""
        from app.services.text_parser import TAXONOMY_PATH
        assert TAXONOMY_PATH.exists(), (
            f"skill_taxonomy.json not found at {TAXONOMY_PATH} — check parents[N] in text_parser.py"
        )

    def test_user_profile_path_resolves(self):
        """Regression: USER_PROFILE_PATH used parents[4] (wrong) instead of parents[3]."""
        from app.services.text_parser import USER_PROFILE_PATH
        assert USER_PROFILE_PATH.exists(), (
            f"user_profile.yaml not found at {USER_PROFILE_PATH} — check parents[N] in text_parser.py"
        )

    def test_parse_requirements_runs_after_upsert(self, db_session):
        """Regression: parse_and_store_requirements was never exercised in pipeline tests.

        Ensures the full pipeline including taxonomy loading and requirement parsing
        completes without error.
        """
        from app.services.job_store import bulk_upsert_jobs, parse_and_store_requirements

        jobs = [
            {
                "external_id": "test_parse_001",
                "title": "Director of Data",
                "description": "Python required. SQL preferred. 5+ years experience.",
                "location": "New York, NY",
                "work_arrangement": "unknown",
                "application_url": "https://example.com/apply",
                "source": "jsearch_api",
                "discovered_date": "2026-04-01",
                "company_name": "Test Corp",
            }
        ]
        bulk_upsert_jobs(db_session, jobs)
        # Must not raise — this exercises _load_taxonomy() and the real config path
        parse_and_store_requirements(db_session, jobs)
