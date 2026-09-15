"""Base class for all company-specific job scrapers."""
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class BaseJobScraper(ABC):
    """
    Subclass for each ATS type (Greenhouse, Lever) or custom career page.
    Subclasses implement fetch_raw() and normalize(); this class handles retries.
    """

    def __init__(self, company: dict[str, Any]) -> None:
        self.company = company
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)"})
        self.last_fetch_succeeded = False
        self.last_error: str | None = None

    def fetch_jobs(self) -> list[dict[str, Any]]:
        """Fetch and normalize all current job listings for this company."""
        try:
            raw = self._fetch_raw()
            normalized = [self.normalize(item) for item in raw]
            self.last_fetch_succeeded = True
            self.last_error = None
            logger.info(
                "Scraped %d jobs from %s", len(normalized), self.company.get("name")
            )
            return normalized
        except Exception as exc:
            self.last_fetch_succeeded = False
            self.last_error = str(exc)
            logger.exception(
                "Scraper failed for company=%s", self.company.get("name")
            )
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    @abstractmethod
    def _fetch_raw(self) -> list[dict[str, Any]]:
        """Fetch raw job data from the source. Retried on failure."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a source-specific raw job record to the standard job dict shape."""
