"""Job discovery via external job search APIs (JSearch via RapidAPI, etc.)."""
import logging
from datetime import date
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import settings

logger = logging.getLogger(__name__)


class JobAPIAggregator:
    """Searches for jobs across configured external APIs and normalizes results."""

    JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
    JSEARCH_HOST = "jsearch.p.rapidapi.com"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-RapidAPI-Key": settings.rapidapi_key,
                "X-RapidAPI-Host": self.JSEARCH_HOST,
            }
        )

    def search_all(self) -> list[dict[str, Any]]:
        """Run all configured search queries and return deduplicated raw results."""
        all_results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for query in settings.search_queries:
            for location in settings.search_locations:
                results = self._search_jsearch(query=query, location=location)
                for job in results:
                    job_id = job.get("job_id", "")
                    if job_id and job_id not in seen_ids:
                        seen_ids.add(job_id)
                        all_results.append(job)

        logger.info("API aggregator fetched %d unique jobs", len(all_results))
        return all_results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _search_jsearch(self, query: str, location: str) -> list[dict[str, Any]]:
        """Search JSearch API for a single query+location pair."""
        import time

        params = {
            "query": f"{query} {location}",
            "num_pages": "1",
            "date_posted": "week",
            "remote_jobs_only": "false",
            "employment_types": "FULLTIME",
        }
        try:
            response = self.session.get(self.JSEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                logger.warning("JSearch returned non-OK status: %s", data.get("status"))
                return []

            time.sleep(settings.api_request_delay_seconds)
            return data.get("data", [])

        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("JSearch rate limit hit for query=%r location=%r", query, location)
            raise

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw JSearch API response item to the standard job dict shape."""
        return {
            "external_id": raw.get("job_id"),
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


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return value[:10]  # ISO date portion
    except Exception:
        return None


def run_job_discovery() -> None:
    """
    Entry point for background job discovery.
    Fetches jobs from all sources, filters, scores, and upserts into the DB.
    """
    # TODO Phase 1: wire up filter + upsert
    # TODO Phase 2: wire up scoring engine
    logger.info("Starting job discovery run")
    aggregator = JobAPIAggregator()
    raw_jobs = aggregator.search_all()
    logger.info("Discovery run complete: %d raw jobs fetched", len(raw_jobs))
