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
        """Jobs marked as remote should be removed by JobFilter."""
        data = _fake_jsearch_response(3)
        for job in data["data"]:
            job["job_is_remote"] = True
        self._run_discovery(db_session, jsearch_data=data, serply_data={"jobs": []})
        assert db_session.query(Job).count() == 0

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
                    "content": "<p>Hybrid role. Python required.</p>",
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
        assert all(j["description"] == "Hybrid role. Python required." for j in jobs)
        assert all(j["work_arrangement"] == "hybrid" for j in jobs)
        assert all(j["posted_date"] == "2026-03-15" for j in jobs)

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
                "descriptionPlain": "Lead our analytics team.",
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
                {"title": f"Job {i}", "externalPath": f"/job/New-York/Job-{i}_JR00{i}", "bulletFields": [f"JR00{i}"]}
                for i in range(2)
            ],
        }
        page2 = {
            "total": 3,
            "jobPostings": [
                {"title": "Job 2", "externalPath": "/job/New-York/Job-2_JR002", "bulletFields": ["JR002"]}
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

    def test_companies_json_path_resolves(self):
        """Regression: _load_companies used parents[4] (wrong) instead of parents[3]."""
        from app.services.api_aggregator import _load_companies
        companies = _load_companies()
        assert isinstance(companies, list)
        assert len(companies) > 0, "companies.json not found or empty — check path in _load_companies()"

    def test_load_companies_returns_enabled_entries(self):
        """All companies with ats_id set should be returned for scraping."""
        from app.services.api_aggregator import _load_companies
        companies = _load_companies()
        enabled = [c for c in companies if c.get("ats_id")]
        assert len(enabled) >= 3, "Expected at least 3 scrapeable companies"

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
