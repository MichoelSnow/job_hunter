"""HTML scraping fallback for companies without a public ATS JSON API."""
import logging
from datetime import date
from typing import Any

from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)


class HtmlScraper(BaseJobScraper):
    """
    Fallback for custom career pages. Requires per-company CSS selectors.
    Most target companies should use Greenhouse or Lever; this handles the rest.
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        url = self.company.get("careers_page_url", "")
        if not url:
            logger.warning("No careers_page_url for company=%s", self.company.get("name"))
            return []

        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        # TODO: implement per-company selector config
        logger.warning(
            "HtmlScraper has no selector config for %s — returning empty", self.company.get("name")
        )
        return []

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": raw.get("id"),
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "location": raw.get("location", ""),
            "work_arrangement": "unknown",
            "application_url": raw.get("url", ""),
            "source": "html_scraper",
            "source_url": raw.get("url"),
            "posted_date": None,
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "raw_data": raw,
        }
