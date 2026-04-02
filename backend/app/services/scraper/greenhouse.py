"""Scraper for companies using the Greenhouse ATS (public boards API)."""
import logging
from datetime import date
from typing import Any

from app.services.job_normalization import html_to_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{ats_id}/jobs"


class GreenhouseScraper(BaseJobScraper):
    """
    Fetches jobs via the public Greenhouse boards JSON API.
    No auth required; returns all open roles for the given ats_id.
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        ats_id = self.company.get("ats_id", "")
        url = GREENHOUSE_API.format(ats_id=ats_id)
        response = self.session.get(url, params={"content": "true"}, timeout=15)
        response.raise_for_status()
        return response.json().get("jobs", [])

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        location = raw.get("location", {})
        location_name = location.get("name") if isinstance(location, dict) else str(location)
        description = html_to_text(raw.get("content"))
        title = raw.get("title") or ""
        return {
            "external_id": f"gh_{raw.get('id')}",
            "title": title,
            "description": description,
            "location": location_name,
            "work_arrangement": infer_work_arrangement(
                title=title,
                location=location_name,
                description=description,
            ),
            "application_url": raw.get("absolute_url") or "",
            "source": "greenhouse",
            "source_url": raw.get("absolute_url"),
            "posted_date": _parse_date(raw.get("first_published") or raw.get("updated_at")),
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "company_industry": self.company.get("industry"),
            "raw_data": raw,
        }


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]
