"""Scraper for companies using the Lever ATS (public postings API)."""
import logging
from datetime import date
from typing import Any

from app.services.job_normalization import html_to_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings/{ats_id}?mode=json"


class LeverScraper(BaseJobScraper):
    """
    Fetches jobs via the public Lever postings JSON API.
    No auth required; returns all published postings for the given ats_id.
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        ats_id = self.company.get("ats_id", "")
        url = LEVER_API.format(ats_id=ats_id)
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        return response.json()

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        categories = raw.get("categories", {})
        title = raw.get("text") or ""
        description = html_to_text(raw.get("descriptionPlain"))
        location = categories.get("location", "")
        return {
            "external_id": f"lv_{raw.get('id')}",
            "title": title,
            "description": description,
            "location": location,
            "work_arrangement": infer_work_arrangement(
                title=title,
                location=location,
                description=description,
            ),
            "application_url": raw.get("applyUrl") or raw.get("hostedUrl", ""),
            "source": "lever",
            "source_url": raw.get("hostedUrl"),
            "posted_date": _parse_timestamp(raw.get("createdAt")),
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "company_industry": self.company.get("industry"),
            "raw_data": raw,
        }


def _parse_timestamp(value: int | None) -> str | None:
    if not value:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(value / 1000).date().isoformat()
