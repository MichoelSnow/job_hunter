"""Job discovery via external job search APIs (JSearch via OpenWebNinja, Serply)."""
import logging
import time
from datetime import date
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import settings

logger = logging.getLogger(__name__)


class JSearchClient:
    """
    JSearch API via OpenWebNinja.
    Docs: https://www.openwebninja.com/api/jsearch/docs
    """

    URL = "https://api.openwebninja.com/jsearch/search"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": settings.jsearchapi_key})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def search(self, query: str, location: str) -> list[dict[str, Any]]:
        params = {"query": f"{query} {location}"}
        try:
            response = self.session.get(self.URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            time.sleep(settings.api_request_delay_seconds)
            return data.get("data", [])
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("JSearch rate limit hit for query=%r location=%r", query, location)
            raise

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": f"js_{raw.get('job_id')}",
            "title": raw.get("job_title", ""),
            "description": raw.get("job_description", ""),
            "location": f"{raw.get('job_city', '')}, {raw.get('job_state', '')}".strip(", "),
            "work_arrangement": "remote" if raw.get("job_is_remote") else "unknown",
            "salary_min": raw.get("job_min_salary"),
            "salary_max": raw.get("job_max_salary"),
            "salary_currency": raw.get("job_salary_currency", "USD"),
            "salary_period": (raw.get("job_salary_period") or "").lower() or None,
            "employment_type": (raw.get("job_employment_type") or "").lower() or None,
            "posted_date": _parse_date(raw.get("job_posted_at_datetime_utc")),
            "discovered_date": date.today().isoformat(),
            "application_url": raw.get("job_apply_link", ""),
            "source": "jsearch_api",
            "source_url": raw.get("job_apply_link"),
            "raw_data": raw,
            "company_name": raw.get("employer_name"),
            "company_logo": raw.get("employer_logo"),
        }


class SerplyClient:
    """
    Serply.io job search API.
    Docs: https://serply.io/docs
    """

    URL = "https://api.serply.io/v1/job/search/"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"X-Api-Key": settings.serplyapi_key})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def search(self, query: str, location: str) -> list[dict[str, Any]]:
        params = {"q": f"{query} {location}", "num": "10"}
        try:
            response = self.session.get(self.URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            time.sleep(settings.api_request_delay_seconds)
            return data.get("jobs", [])
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("Serply rate limit hit for query=%r location=%r", query, location)
            raise

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": f"sp_{raw.get('job_id') or raw.get('link', '')[-32:]}",
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "location": raw.get("location", ""),
            "work_arrangement": "unknown",
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "USD",
            "salary_period": None,
            "employment_type": None,
            "posted_date": raw.get("date_posted"),
            "discovered_date": date.today().isoformat(),
            "application_url": raw.get("link", ""),
            "source": "serply_api",
            "source_url": raw.get("link"),
            "raw_data": raw,
            "company_name": raw.get("company_name"),
            "company_logo": None,
        }


class JobAPIAggregator:
    """Runs all configured search queries across all enabled API clients."""

    def __init__(self) -> None:
        self.clients: list[tuple[Any, str]] = []
        if settings.jsearchapi_key:
            self.clients.append((JSearchClient(), "JSearch"))
        if settings.serplyapi_key:
            self.clients.append((SerplyClient(), "Serply"))
        if not self.clients:
            logger.warning("No API keys configured — job discovery will return no results")

    def search_all(self) -> list[dict[str, Any]]:
        """Run all queries across all clients; deduplicate by external_id."""
        all_results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for client, name in self.clients:
            for query in settings.search_queries:
                for location in settings.search_locations:
                    try:
                        raw_jobs = client.search(query=query, location=location)
                        for raw in raw_jobs:
                            normalized = client.normalize(raw)
                            ext_id = normalized.get("external_id", "")
                            if ext_id and ext_id not in seen_ids:
                                seen_ids.add(ext_id)
                                all_results.append(normalized)
                    except Exception:
                        logger.exception(
                            "%s search failed for query=%r location=%r", name, query, location
                        )

        logger.info("API aggregator fetched %d unique jobs", len(all_results))
        return all_results


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _load_companies() -> list[dict]:
    """Load company seed list from config/companies.json."""
    import json
    from pathlib import Path

    path = Path(__file__).parents[4] / "config" / "companies.json"
    if not path.exists():
        logger.warning("companies.json not found at %s", path)
        return []
    with path.open() as f:
        return json.load(f).get("companies", [])


def run_company_scrape() -> list[dict]:
    """
    Scrape all companies in companies.json that have an ats_id set.
    Companies with ats_type='custom' and no ats_id are skipped until
    their HTML selectors are configured.
    Returns a list of normalized job dicts.
    """
    from app.services.scraper import get_scraper

    companies = _load_companies()
    enabled = [c for c in companies if c.get("ats_id")]

    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    for company in enabled:
        scraper = get_scraper(company)
        jobs = scraper.fetch_jobs()
        for job in jobs:
            ext_id = job.get("external_id", "")
            if ext_id and ext_id not in seen_ids:
                seen_ids.add(ext_id)
                all_jobs.append(job)

    logger.info("Company scrape complete: %d unique jobs from %d companies", len(all_jobs), len(enabled))
    return all_jobs


def run_job_discovery() -> None:
    """
    Full job discovery pipeline:
      1. Fetch from external APIs (JSearch, Serply)
      2. Fetch from company ATS scrapers (Greenhouse, Lever)
      3. Apply hard filters (location, work arrangement, role level)
      4. Upsert filtered jobs into the database
      5. Record API usage
    """
    from app.db.session import SessionLocal
    from app.services.job_filter import JobFilter
    from app.services.job_store import bulk_upsert_jobs, record_api_usage

    logger.info("Starting job discovery run")

    api_jobs = JobAPIAggregator().search_all()
    scraped_jobs = run_company_scrape()
    all_jobs = api_jobs + scraped_jobs

    logger.info(
        "Fetched %d API jobs + %d scraped jobs = %d total",
        len(api_jobs),
        len(scraped_jobs),
        len(all_jobs),
    )

    filtered_jobs = JobFilter().apply_all(all_jobs)

    db = SessionLocal()
    try:
        inserted, updated = bulk_upsert_jobs(db, filtered_jobs)

        # Record one usage row per source present in this run
        sources: dict[str, int] = {}
        for job in all_jobs:
            sources[job.get("source", "unknown")] = sources.get(job.get("source", "unknown"), 0) + 1
        for source, count in sources.items():
            record_api_usage(db, api_name=source, request_count=count)
        db.commit()

        # Parse requirements and score all active jobs
        from app.services.job_store import parse_and_store_requirements
        from app.services.scoring_engine import ScoringEngine
        from app.services.text_parser import load_user_profile

        parse_and_store_requirements(db, filtered_jobs)

        user_profile = load_user_profile()
        engine = ScoringEngine(settings, user_profile)
        _score_all_active_jobs(db, engine)
    finally:
        db.close()

    logger.info(
        "Discovery run complete: %d inserted, %d updated, %d filtered out",
        inserted,
        updated,
        len(all_jobs) - len(filtered_jobs),
    )


def _score_all_active_jobs(db: "Session", engine: "ScoringEngine") -> None:
    """
    Score every active job in the DB using stored requirements.
    Writes match scores back to each Job row and commits.
    """
    from datetime import datetime

    from sqlalchemy.orm import Session  # noqa: F401 — type reference only

    from app.models.criteria import UserCriteria
    from app.models.job import Job as JobModel
    from app.services.scoring_engine import ScoringEngine  # noqa: F401 — type reference only

    criteria = [
        {
            "criterion_type": c.criterion_type,
            "criterion_value": c.criterion_value,
            "is_hard_requirement": c.is_hard_requirement,
            "weight": c.weight,
        }
        for c in db.query(UserCriteria).all()
    ]

    jobs = db.query(JobModel).filter(JobModel.is_active == True).all()  # noqa: E712
    for job in jobs:
        required_skills = [
            r.requirement_value
            for r in job.requirements
            if r.requirement_type == "skill" and r.is_required
        ]
        experience_required = next(
            (int(r.requirement_value) for r in job.requirements if r.requirement_type == "experience"),
            None,
        )
        job_dict = {
            "title": job.title,
            "required_skills": required_skills,
            "experience_required": experience_required,
            "salary_min": job.salary_min,
            "company_industry": None,  # TODO: add industry to Company model
        }
        u2j, j2u, overall = engine.score(job_dict, criteria)
        job.match_score_user_to_job = u2j
        job.match_score_job_to_user = j2u
        job.overall_match_score = overall
        job.score_calculated_at = datetime.utcnow()

    db.commit()
    logger.info("Scored %d active jobs", len(jobs))
