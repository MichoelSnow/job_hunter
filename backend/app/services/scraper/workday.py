"""Scraper for companies using the Workday ATS (internal JSON API).

Workday exposes a consistent POST endpoint across all tenants:
  https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs

The tenant name, WD instance number (wd1, wd5, etc.), and board name are found
by inspecting the Network tab in browser DevTools on the company's careers page.

Company config shape (in companies.json):
  {
    "ats_type": "workday",
    "ats_id": "{tenant}",
    "workday_board": "{board}",
    "workday_instance": "wd5"   // defaults to "wd1" if omitted
  }
"""
import logging
from datetime import date
from typing import Any

from app.services.job_normalization import infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100


class WorkdayScraper(BaseJobScraper):
    """
    Fetches all job postings via the Workday internal jobs API.
    Paginates automatically until all results are retrieved.
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        tenant = self.company.get("ats_id", "")
        board = self.company.get("workday_board", "")
        instance = self.company.get("workday_instance", "wd1")

        if not tenant or not board:
            logger.warning(
                "WorkdayScraper: missing ats_id or workday_board for %s — skipping",
                self.company.get("name"),
            )
            return []

        base_url = f"https://{tenant}.{instance}.myworkdayjobs.com"
        url = f"{base_url}/wday/cxs/{tenant}/{board}/jobs"

        # Workday requires a CSRF token obtained by loading the careers page first.
        # The token is set as a cookie (CALYPSO_CSRF_TOKEN) and must be echoed back
        # in the x-calypso-csrf-token request header.
        self.session.get(f"{base_url}/{board}", timeout=15)
        csrf_token = self.session.cookies.get("CALYPSO_CSRF_TOKEN", "")
        headers = {"x-calypso-csrf-token": csrf_token} if csrf_token else {}

        all_jobs: list[dict[str, Any]] = []
        offset = 0

        while True:
            payload = {
                "limit": _PAGE_SIZE,
                "offset": offset,
                "searchText": "",
                "appliedFacets": {},
            }
            response = self.session.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            page = data.get("jobPostings", [])
            all_jobs.extend(page)

            total = data.get("total", 0)
            offset += len(page)
            if offset >= total or not page:
                break

        return all_jobs

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        tenant = self.company.get("ats_id", "")
        board = self.company.get("workday_board", "")
        instance = self.company.get("workday_instance", "wd1")
        external_path = raw.get("externalPath", "")

        apply_url = (
            f"https://{tenant}.{instance}.myworkdayjobs.com/{board}{external_path}"
            if external_path
            else ""
        )

        # bulletFields[0] is the job requisition ID when present
        bullet_fields = raw.get("bulletFields") or []
        req_id = bullet_fields[0] if bullet_fields else ""
        external_id = f"wd_{tenant}_{req_id}" if req_id else f"wd_{tenant}_{external_path.split('_')[-1]}"

        title = raw.get("title") or ""
        location = raw.get("locationsText", "")
        return {
            "external_id": external_id,
            "title": title,
            "description": "",
            "location": location,
            "work_arrangement": infer_work_arrangement(
                title=title,
                location=location,
                description="",
            ),
            "application_url": apply_url,
            "source": "workday",
            "source_url": apply_url,
            "posted_date": None,
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "company_industry": self.company.get("industry"),
            "raw_data": raw,
        }
