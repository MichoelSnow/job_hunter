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
    """End-to-end pipeline tests with mocked HTTP."""

    def _run_pipeline(self, db_session, jsearch_data=None, serply_data=None):
        """Run bulk_upsert_jobs with fake normalized job dicts derived from mocked API data."""
        from app.services.api_aggregator import JobAPIAggregator
        from app.services.job_filter import JobFilter
        from app.services.job_store import bulk_upsert_jobs

        jsearch_resp = _mock_http_response(jsearch_data or _fake_jsearch_response())
        serply_resp = _mock_http_response(serply_data or _fake_serply_response())

        with patch("app.services.api_aggregator.settings") as mock_settings, \
             patch("requests.Session.get") as mock_get:

            mock_settings.jsearchapi_key = "fake_key"
            mock_settings.serplyapi_key = "fake_key"
            mock_settings.jsearch_num_pages = 1
            mock_settings.serply_num_results = 10
            mock_settings.search_queries = ["director data healthcare New York"]
            mock_settings.search_locations = ["New York, NY"]
            mock_settings.api_request_delay_seconds = 0

            # First call → JSearch, second → Serply
            mock_get.side_effect = [jsearch_resp, serply_resp]

            aggregator = JobAPIAggregator()
            raw_jobs = aggregator.search_all()

        filtered = JobFilter().apply_all(raw_jobs)
        inserted, updated = bulk_upsert_jobs(db_session, filtered)
        return inserted, updated, filtered

    def test_full_pipeline_inserts_jobs(self, db_session):
        inserted, updated, filtered = self._run_pipeline(db_session)
        assert inserted > 0
        assert updated == 0

    def test_second_run_updates_not_inserts(self, db_session):
        self._run_pipeline(db_session)
        inserted, updated, _ = self._run_pipeline(db_session)
        assert inserted == 0
        assert updated > 0

    def test_company_rows_created(self, db_session):
        self._run_pipeline(db_session)
        count = db_session.query(Company).count()
        assert count > 0

    def test_scraper_enabled_default_set(self, db_session):
        """Regression: scraper_enabled NOT NULL was missing from ORM, causing live DB failures."""
        self._run_pipeline(db_session)
        companies = db_session.query(Company).all()
        assert all(c.scraper_enabled is True for c in companies)

    def test_jobs_have_correct_source(self, db_session):
        self._run_pipeline(db_session)
        sources = {j.source for j in db_session.query(Job).all()}
        assert "jsearch_api" in sources

    def test_remote_jobs_filtered_out(self, db_session):
        """Jobs marked as remote should be removed by JobFilter."""
        data = _fake_jsearch_response(3)
        for job in data["data"]:
            job["job_is_remote"] = True
        inserted, _, _ = self._run_pipeline(db_session, jsearch_data=data, serply_data={"jobs": []})
        assert inserted == 0


class TestCompanyScrape:
    """Smoke tests for company ATS scraping with mocked HTTP."""

    def _make_greenhouse_response(self, n: int = 5) -> dict:
        return {
            "jobs": [
                {
                    "id": i,
                    "title": f"Director of Data {i}",
                    "location": {"name": "New York, NY"},
                    "absolute_url": f"https://boards.greenhouse.io/testco/jobs/{i}",
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
        assert all(j["source"] == "greenhouse" for j in jobs)
        assert all(j["external_id"].startswith("gh_") for j in jobs)
        assert all(j["company_name"] == "Test Co" for j in jobs)

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

        with patch("requests.Session.post") as mock_post:
            mock_post.side_effect = [
                _mock_http_response(page1),
                _mock_http_response(page2),
            ]
            jobs = scraper.fetch_jobs()

        assert len(jobs) == 3
        assert mock_post.call_count == 2  # confirmed pagination
        assert all(j["source"] == "workday" for j in jobs)

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
