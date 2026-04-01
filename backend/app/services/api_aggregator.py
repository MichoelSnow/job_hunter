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
