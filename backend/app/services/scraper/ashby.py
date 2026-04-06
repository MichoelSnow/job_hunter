"""Scraper for companies using Ashby public posting API."""
import logging
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from app.services.job_normalization import extract_salary_from_text, html_to_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

ASHBY_POSTING_API = "https://api.ashbyhq.com/posting-api/job-board/{job_board_name}"
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)


class AshbyScraper(BaseJobScraper):
    """
    Fetches jobs via Ashby's public posting API using the organization
    hosted jobs page name (e.g. "allarahealth").
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        org = _organization_name(self.company)
        if not org:
            logger.warning(
                "AshbyScraper: missing ats_id/careers_url org for %s; skipping",
                self.company.get("name"),
            )
            return []

        url = ASHBY_POSTING_API.format(job_board_name=org)
        response = self.session.get(url, params={"includeCompensation": "true"}, timeout=15)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            logger.warning("AshbyScraper: unexpected response shape for %s", self.company.get("name"))
            return []
        return jobs

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        org = _organization_name(self.company)
        job_url = str(raw.get("jobUrl") or "").strip()
        apply_url = str(raw.get("applyUrl") or "").strip()
        job_id = _extract_job_id(raw, job_url, apply_url)
        if not job_url and org and job_id:
            job_url = f"https://jobs.ashbyhq.com/{org}/{job_id}"

        title = raw.get("title") or ""
        location = raw.get("location") or ""
        description = raw.get("descriptionPlain") or html_to_text(raw.get("descriptionHtml"))
        salary_min, salary_max, salary_period, salary_currency = _extract_salary(raw)
        workplace_type = (raw.get("workplaceType") or "").lower()
        return {
            "external_id": f"as_{job_id}" if job_id else "",
            "title": title,
            "description": description,
            "location": location,
            "work_arrangement": infer_work_arrangement(
                title=title,
                location=location,
                description=description,
                is_remote=bool(raw.get("isRemote")) or workplace_type == "remote",
            ),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": salary_currency or "USD",
            "salary_period": salary_period,
            "employment_type": (raw.get("employmentType") or "").lower() or None,
            "application_url": job_url or apply_url,
            "source": "ashby",
            "source_url": job_url or None,
            "posted_date": _parse_date(raw.get("publishedAt")),
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "company_industry": self.company.get("industry"),
            "raw_data": raw,
        }


def _organization_name(company: dict[str, Any]) -> str:
    ats_id = (company.get("ats_id") or "").strip()
    if ats_id:
        return ats_id

    careers_url = (company.get("careers_url") or "").strip()
    if not careers_url:
        return ""
    parsed = urlparse(careers_url)
    parts = [p for p in parsed.path.split("/") if p]
    return parts[0] if parts else ""


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _extract_job_id(raw: dict[str, Any], job_url: str, apply_url: str) -> str:
    for candidate in (raw.get("id"),):
        if candidate:
            return str(candidate)

    for url in (job_url, apply_url):
        if not url:
            continue
        match = _UUID_RE.search(url)
        if match:
            return match.group(0)
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return parts[-1]
    return ""


def _extract_salary(raw: dict[str, Any]) -> tuple[int | None, int | None, str | None, str | None]:
    compensation = raw.get("compensation")
    if isinstance(compensation, dict):
        summary = (
            compensation.get("scrapeableCompensationSalarySummary")
            or compensation.get("compensationTierSummary")
        )
        parsed = extract_salary_from_text(summary)
        if parsed[0] is not None or parsed[1] is not None:
            return parsed

        for component in compensation.get("summaryComponents") or []:
            if not isinstance(component, dict):
                continue
            if (component.get("compensationType") or "").lower() != "salary":
                continue
            interval = (component.get("interval") or "").lower()
            period = "year" if "year" in interval else ("hour" if "hour" in interval else None)
            return (
                _to_int(component.get("minValue")),
                _to_int(component.get("maxValue")),
                period,
                component.get("currencyCode"),
            )

    return extract_salary_from_text(raw.get("compensationTierSummary"))


def _to_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
