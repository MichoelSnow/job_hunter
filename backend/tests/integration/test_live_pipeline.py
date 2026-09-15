"""Live end-to-end pipeline test.

Makes a SINGLE real JSearch API request and runs the COMPLETE pipeline
(fetch → filter → upsert → parse requirements → score) via run_job_discovery().
All company scrapers and Serply are mocked to return empty — only JSearch is live.

This catches bugs that only appear with real API data (null fields, unexpected
response shapes) AND bugs in later pipeline steps (path resolution, scoring,
parsing) that unit tests with fake data can miss.

Marked `live` — excluded from the default pytest run.
To run explicitly (load .env first):
    set -a; source .env; set +a
    poetry run pytest -m live -v -s
"""

import os
from unittest.mock import MagicMock, patch

import app.models  # noqa: F401
import pytest
from app.db.base import Base
from app.models.job import Job, JobRequirement
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.live


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


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def test_live_full_pipeline(db_session):
    """
    Runs the complete run_job_discovery() pipeline with one real JSearch request.
    All scrapers and Serply return empty — cost is exactly 1 API call.

    Verifies:
    - Pipeline completes without raising
    - discovery_status ends as 'complete' (not 'error')
    - All DB jobs satisfy NOT NULL constraints
    - Requirement parsing and scoring ran without error
    """
    if not os.environ.get("JSEARCHAPI_KEY"):
        pytest.skip("JSEARCHAPI_KEY not set")

    from app.services.api_aggregator import discovery_status, run_job_discovery

    real_jsearch_key = os.environ["JSEARCHAPI_KEY"]

    # Intercept all HTTP; let only JSearch through
    def dispatch_get(url, **kwargs):
        if "openwebninja" in url:
            # Real JSearch call — use the actual requests library
            import requests as _requests

            session = _requests.Session()
            session.headers.update({"x-api-key": real_jsearch_key})
            return session.get(url, **kwargs)
        # Greenhouse, Lever, Workday CSRF, anything else — return empty
        if "greenhouse" in url:
            return _mock_response({"jobs": []})
        if "lever" in url:
            return _mock_response([])
        return _mock_response({})

    db_session.close = lambda: None  # prevent run_job_discovery from closing our test session

    with (
        patch("app.services.api_aggregator.settings") as mock_settings,
        patch("app.db.session.SessionLocal", return_value=db_session),
        patch("requests.Session.get", side_effect=dispatch_get),
        patch(
            "requests.Session.post", return_value=_mock_response({"total": 0, "jobPostings": []})
        ),
    ):
        mock_settings.jsearchapi_key = real_jsearch_key
        mock_settings.serplyapi_key = ""  # disabled — no Serply calls
        mock_settings.jsearch_num_pages = 1
        mock_settings.serply_num_results = 10
        mock_settings.search_queries = ["director data healthcare"]
        mock_settings.search_locations = ["New York, NY"]
        mock_settings.api_request_delay_seconds = 0
        mock_settings.user_to_job_weight = 0.6
        mock_settings.job_to_user_weight = 0.4
        mock_settings.skill_match_weight = 0.50
        mock_settings.experience_match_weight = 0.25
        mock_settings.title_match_weight = 0.15
        mock_settings.education_match_weight = 0.10

        run_job_discovery()

    assert discovery_status["status"] == "complete", (
        f"Pipeline ended with status={discovery_status['status']!r}: "
        f"{discovery_status.get('error')}"
    )

    jobs = db_session.query(Job).all()
    # JSearch may return jobs that all get filtered — that's valid, pipeline must still complete
    for job in jobs:
        assert job.title is not None and job.title != "", f"job {job.id}: null/empty title"
        assert job.description is not None, f"job {job.id}: null description"
        assert job.application_url is not None and job.application_url != "", (
            f"job {job.id}: null application_url"
        )
        assert job.source is not None, f"job {job.id}: null source"
        assert job.discovered_date is not None, f"job {job.id}: null discovered_date"

    # Requirement parsing ran — even if zero rows, it must not have raised
    req_count = db_session.query(JobRequirement).count()
    assert req_count >= 0
