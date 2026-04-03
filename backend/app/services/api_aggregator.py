"""Job discovery via external job search APIs (JSearch via OpenWebNinja, Serply)."""
import logging
import time
from datetime import date, datetime
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import settings
from app.services.job_normalization import html_to_text, infer_work_arrangement

logger = logging.getLogger(__name__)

# Module-level status — single-user app, in-memory is sufficient.
# Shape is intentionally simple so the API endpoint can return it directly.
discovery_status: dict[str, Any] = {
    "status": "idle",  # idle | running | complete | error
    "mode": None,  # full | api | scrapers
    "step": None,
    "started_at": None,
    "completed_at": None,
    "inserted": None,
    "updated": None,
    "filtered_out": None,
    "error": None,
}


def _set_status(**kwargs: Any) -> None:
    discovery_status.update(kwargs)


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
        # num_pages bundles multiple result pages into one HTTP response (each page = 10 jobs).
        # Values 1–10 cost 2× quota; 11–20 cost 3× quota. Default of 10 → 100 results at 2× cost.
        params = {
            "query": f"{query} {location}",
            "num_pages": settings.jsearch_num_pages,
        }
        try:
            response = self.session.get(self.URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            time.sleep(settings.api_request_delay_seconds)
            return data.get("data", [])
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("JSearch rate limit hit for query=%r location=%r", query, location)
            raise

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        description = html_to_text(raw.get("job_description"))
        location = f"{raw.get('job_city', '')}, {raw.get('job_state', '')}".strip(", ")
        return {
            "external_id": f"js_{raw.get('job_id')}",
            "title": raw.get("job_title") or "",
            "description": description,
            "location": location,
            "work_arrangement": infer_work_arrangement(
                title=raw.get("job_title"),
                location=location,
                description=description,
                is_remote=raw.get("job_is_remote"),
            ),
            "salary_min": raw.get("job_min_salary"),
            "salary_max": raw.get("job_max_salary"),
            "salary_currency": raw.get("job_salary_currency") or "USD",
            "salary_period": (raw.get("job_salary_period") or "").lower() or None,
            "employment_type": (raw.get("job_employment_type") or "").lower() or None,
            "posted_date": _parse_date(raw.get("job_posted_at_datetime_utc")),
            "discovered_date": date.today().isoformat(),
            "application_url": raw.get("job_apply_link") or "",
            "source": "jsearch_api",
            "source_url": raw.get("job_apply_link"),
            "raw_data": raw,
            "company_name": raw.get("employer_name"),
            "company_logo": raw.get("employer_logo"),
            "company_industry": None,
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
        # num / per_page: Serply supports up to 100 results per request.
        params = {"q": f"{query} {location}", "num": str(settings.serply_num_results)}
        try:
            response = self.session.get(self.URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            time.sleep(settings.api_request_delay_seconds)
            return data.get("jobs", [])
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("Serply rate limit hit for query=%r location=%r", query, location)
            raise

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        description = html_to_text(raw.get("description"))
        location = raw.get("location") or ""
        return {
            "external_id": f"sp_{raw.get('job_id') or raw.get('link', '')[-32:]}",
            "title": raw.get("title") or "",
            "description": description,
            "location": location,
            "work_arrangement": infer_work_arrangement(
                title=raw.get("title"),
                location=location,
                description=description,
            ),
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
            "company_industry": None,
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


def _load_companies_for_scrape() -> list[dict]:
    """
    Load scrape targets from DB (Companies page state).
    """
    from app.db.session import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    try:
        rows = db.query(Company).filter(Company.scraper_enabled == True).all()  # noqa: E712
        companies: list[dict] = []
        for row in rows:
            merged = {
                "name": row.name,
                "industry": row.industry,
                # DB is authoritative for user-editable scrape fields.
                "ats_type": row.ats_type,
                "ats_id": row.ats_id,
                "careers_url": row.careers_page_url or row.website_url,
                "workday_board": row.workday_board,
                "workday_instance": row.workday_instance,
                "html_selectors": row.html_selectors,
            }
            companies.append(merged)
        return companies
    finally:
        db.close()


def _source_for_company(company: dict[str, Any]) -> str:
    ats_type = (company.get("ats_type") or "custom").lower()
    if ats_type in {"greenhouse", "lever", "workday", "ashby"}:
        return ats_type
    return "html_scraper"


def get_scrape_targets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Build scraper targets from DB companies and return:
      - enabled targets
      - skipped targets with reason
    """
    companies = _load_companies_for_scrape()
    enabled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for company in companies:
        ats_type = (company.get("ats_type") or "").strip().lower()
        if ats_type in {"greenhouse", "lever", "workday", "ashby"}:
            if company.get("ats_id"):
                enabled.append(company)
            else:
                skipped.append(
                    {
                        "name": company.get("name"),
                        "reason": "missing ats_id",
                        "ats_type": ats_type,
                    }
                )
            continue

        if ats_type in {"custom", "html"}:
            has_careers = bool(company.get("careers_url"))
            has_selectors = bool(company.get("html_selectors"))
            if has_careers and has_selectors:
                enabled.append(company)
            else:
                missing_parts: list[str] = []
                if not has_careers:
                    missing_parts.append("careers_url")
                if not has_selectors:
                    missing_parts.append("html_selectors")
                skipped.append(
                    {
                        "name": company.get("name"),
                        "reason": f"missing {', '.join(missing_parts)}",
                        "ats_type": ats_type or None,
                    }
                )
            continue

        skipped.append(
            {
                "name": company.get("name"),
                "reason": "missing or unsupported ats_type",
                "ats_type": ats_type or None,
            }
        )

    return enabled, skipped


def run_company_scrape() -> tuple[list[dict], dict[tuple[str, str], set[str]]]:
    """
    Scrape all enabled companies from the DB (Companies page settings).
    Returns:
      - list of normalized job dicts
      - observed external_ids per (company_name, source) for successful scrapes
    """
    from app.services.scraper import get_scraper

    enabled, skipped = get_scrape_targets()
    if skipped:
        logger.info("Skipping %d companies for scrape due to missing config", len(skipped))
        for item in skipped:
            logger.info(
                "Skipped company=%s ats_type=%s reason=%s",
                item.get("name"),
                item.get("ats_type"),
                item.get("reason"),
            )

    all_jobs: list[dict] = []
    seen_ids: set[str] = set()
    observed_external_ids: dict[tuple[str, str], set[str]] = {}

    for i, company in enumerate(enabled, 1):
        name = company.get("name", "unknown")
        _set_status(step=f"Scraping {name} ({i}/{len(enabled)})")
        scraper = get_scraper(company)
        jobs = scraper.fetch_jobs()
        if scraper.last_fetch_succeeded:
            key = (name, _source_for_company(company))
            observed_external_ids[key] = {
                job.get("external_id", "")
                for job in jobs
                if job.get("external_id")
            }
        for job in jobs:
            ext_id = job.get("external_id", "")
            if ext_id and ext_id not in seen_ids:
                seen_ids.add(ext_id)
                all_jobs.append(job)

    logger.info("Company scrape complete: %d unique jobs from %d companies", len(all_jobs), len(enabled))
    return all_jobs, observed_external_ids


def _run_job_discovery(*, fetch_api: bool, fetch_scrapers: bool, mode: str) -> None:
    """
    Job discovery pipeline with selectable sources.
    """
    from app.db.session import SessionLocal
    from app.services.job_filter import JobFilter
    from app.services.job_store import (
        bulk_upsert_jobs,
        mark_missing_scraped_jobs_closed,
        record_api_usage,
    )

    if not fetch_api and not fetch_scrapers:
        raise ValueError("At least one discovery source must be enabled")

    initial_step = "Fetching from job search APIs..." if fetch_api else "Scraping company job boards..."
    _set_status(
        status="running",
        mode=mode,
        step=initial_step,
        started_at=datetime.utcnow().isoformat(),
        completed_at=None,
        inserted=None,
        updated=None,
        filtered_out=None,
        error=None,
    )
    logger.info("Starting job discovery run (mode=%s)", mode)

    try:
        api_jobs = JobAPIAggregator().search_all() if fetch_api else []

        scraped_jobs: list[dict] = []
        observed_scraped_ids: dict[tuple[str, str], set[str]] = {}
        if fetch_scrapers:
            _set_status(step="Scraping company job boards...")
            scraped_jobs, observed_scraped_ids = run_company_scrape()
        all_jobs = api_jobs + scraped_jobs

        logger.info(
            "Fetched %d API jobs + %d scraped jobs = %d total (mode=%s)",
            len(api_jobs),
            len(scraped_jobs),
            len(all_jobs),
            mode,
        )

        _set_status(step="Filtering jobs...")
        filtered_jobs = JobFilter().apply_all(all_jobs)

        _set_status(step="Saving to database...")
        db = SessionLocal()
        try:
            inserted, updated = bulk_upsert_jobs(db, filtered_jobs)
            if fetch_scrapers:
                mark_missing_scraped_jobs_closed(
                    db,
                    observed_external_ids=observed_scraped_ids,
                    closed_on=date.today(),
                )

            sources: dict[str, int] = {}
            for job in all_jobs:
                sources[job.get("source", "unknown")] = sources.get(job.get("source", "unknown"), 0) + 1
            for source, count in sources.items():
                record_api_usage(db, api_name=source, request_count=count)
            db.commit()

            _set_status(step="Parsing job requirements...")
            from app.services.job_store import parse_and_store_requirements
            from app.services.scoring_engine import ScoringEngine
            from app.services.text_parser import load_user_profile

            parse_and_store_requirements(db, filtered_jobs)

            _set_status(step="Scoring jobs...")
            user_profile = load_user_profile()
            engine = ScoringEngine(settings, user_profile)
            _score_all_active_jobs(db, engine)
        finally:
            db.close()

        filtered_out = len(all_jobs) - len(filtered_jobs)
        _set_status(
            status="complete",
            mode=mode,
            step=None,
            completed_at=datetime.utcnow().isoformat(),
            inserted=inserted,
            updated=updated,
            filtered_out=filtered_out,
        )
        logger.info(
            "Discovery run complete (mode=%s): %d inserted, %d updated, %d filtered out",
            mode,
            inserted,
            updated,
            filtered_out,
        )

    except Exception as exc:
        _set_status(
            status="error",
            mode=mode,
            step=None,
            completed_at=datetime.utcnow().isoformat(),
            error=str(exc),
        )
        logger.exception("Job discovery run failed (mode=%s)", mode)


def run_job_discovery() -> None:
    """Run full discovery (paid APIs + scrapers)."""
    _run_job_discovery(fetch_api=True, fetch_scrapers=True, mode="full")


def run_job_discovery_api_only() -> None:
    """Run discovery from paid APIs only (JSearch + Serply)."""
    _run_job_discovery(fetch_api=True, fetch_scrapers=False, mode="api")


def run_job_discovery_scrapers_only() -> None:
    """Run discovery from company ATS scrapers only."""
    _run_job_discovery(fetch_api=False, fetch_scrapers=True, mode="scrapers")


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
            "company_industry": job.company.industry if job.company else None,
        }
        u2j, j2u, overall = engine.score(job_dict, criteria)
        job.match_score_user_to_job = u2j
        job.match_score_job_to_user = j2u
        job.overall_match_score = overall
        job.score_calculated_at = datetime.utcnow()

    db.commit()
    logger.info("Scored %d active jobs", len(jobs))
