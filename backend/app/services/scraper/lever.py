"""Scraper for companies using the Lever ATS (public postings API)."""
import html
import logging
from datetime import date
from typing import Any

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.services.job_normalization import extract_salary_from_text, html_to_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings/{ats_id}?mode=json"
_LEVER_TIMEOUT_SECONDS = 30


class LeverScraper(BaseJobScraper):
    """
    Fetches jobs via the public Lever postings JSON API.
    No auth required; returns all published postings for the given ats_id.
    """

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=12),
        retry=retry_if_exception(lambda exc: _is_retryable_lever_exception(exc)),
        reraise=True,
    )
    def _fetch_raw(self) -> list[dict[str, Any]]:
        ats_id = self.company.get("ats_id", "")
        url = LEVER_API.format(ats_id=ats_id)
        response = self.session.get(url, timeout=_LEVER_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        categories = raw.get("categories", {})
        title = raw.get("text") or ""
        description = _compose_description_text(raw)
        description_html = _compose_description_html(raw)
        location = categories.get("location", "")
        salary_min, salary_max, salary_period, salary_currency = extract_salary_from_text(description)
        normalized_raw = dict(raw)
        normalized_raw["normalized_description_html"] = description_html
        hosted_url = raw.get("hostedUrl") or ""
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
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": salary_currency or "USD",
            "salary_period": salary_period,
            "application_url": hosted_url or raw.get("applyUrl") or "",
            "source": "lever",
            "source_url": hosted_url,
            "posted_date": _parse_timestamp(raw.get("createdAt")),
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "company_industry": self.company.get("industry"),
            "raw_data": normalized_raw,
        }


def _parse_timestamp(value: int | None) -> str | None:
    if not value:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(value / 1000).date().isoformat()


def _compose_description_text(raw: dict[str, Any]) -> str:
    chunks: list[str] = []
    seen: set[str] = set()

    def append_unique(value: str | None) -> None:
        normalized = html_to_text(value)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        chunks.append(normalized)

    append_unique(raw.get("descriptionPlain"))
    append_unique(raw.get("descriptionBodyPlain"))
    append_unique(raw.get("openingPlain"))
    append_unique(raw.get("additionalPlain"))

    for section in raw.get("lists") or []:
        if not isinstance(section, dict):
            continue
        heading = html_to_text(section.get("text"))
        content = html_to_text(section.get("content"))
        if heading and content:
            append_unique(f"{heading} {content}")
        elif heading:
            append_unique(heading)
        elif content:
            append_unique(content)

    if not chunks:
        append_unique(raw.get("description"))
        append_unique(raw.get("descriptionBody"))
        append_unique(raw.get("opening"))
        append_unique(raw.get("additional"))

    return "\n\n".join(chunks)


def _compose_description_html(raw: dict[str, Any]) -> str:
    blocks: list[str] = []
    seen_plain: set[str] = set()

    def append_html(value: str | None) -> None:
        if not value:
            return
        plain = html_to_text(value)
        if not plain or plain in seen_plain:
            return
        seen_plain.add(plain)
        blocks.append(str(value))

    append_html(raw.get("description"))
    append_html(raw.get("descriptionBody"))
    append_html(raw.get("opening"))
    append_html(raw.get("additional"))

    for section in raw.get("lists") or []:
        if not isinstance(section, dict):
            continue
        heading = html_to_text(section.get("text"))
        content = section.get("content")
        if not heading and not content:
            continue
        heading_html = f"<h3>{html.escape(heading)}</h3>" if heading else ""
        content_html = f"<ul>{content}</ul>" if content else ""
        append_html(f"{heading_html}{content_html}")

    if not blocks:
        append_html(raw.get("descriptionPlain"))
        append_html(raw.get("descriptionBodyPlain"))
        append_html(raw.get("openingPlain"))
        append_html(raw.get("additionalPlain"))

    return "\n".join(blocks)


def _is_retryable_lever_exception(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout)):
        return True
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        response = getattr(exc, "response", None)
        if response is None:
            return False
        return response.status_code in {429, 500, 502, 503, 504}
    return False
