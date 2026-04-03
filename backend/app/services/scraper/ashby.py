"""Scraper for companies using Ashby job boards (non-user GraphQL endpoint)."""
import logging
from datetime import date
from typing import Any
from urllib.parse import urlparse

from app.services.job_normalization import extract_salary_from_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

ASHBY_API_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
_ASHBY_QUERY = """query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
  ) {
    teams {
      id
      name
      externalName
      parentTeamId
      __typename
    }
    jobPostings {
      id
      title
      teamId
      locationId
      locationName
      workplaceType
      employmentType
      secondaryLocations {
        ...JobPostingSecondaryLocationParts
        __typename
      }
      compensationTierSummary
      __typename
    }
    __typename
  }
}

fragment JobPostingSecondaryLocationParts on JobPostingSecondaryLocation {
  locationId
  locationName
  __typename
}"""


class AshbyScraper(BaseJobScraper):
    """
    Fetches jobs via Ashby's non-user GraphQL endpoint using the organization
    hosted jobs page name (e.g. "allarahealth").
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        org = _organization_name(self.company)
        if not org:
            logger.warning(
                "AshbyScraper: missing ats_id/careers_url org for %s — skipping",
                self.company.get("name"),
            )
            return []

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "apollographql-client-name": "frontend_non_user",
            "apollographql-client-version": "0.1.0",
            "Origin": "https://jobs.ashbyhq.com",
            "Referer": f"https://jobs.ashbyhq.com/{org}",
        }
        payload = {
            "operationName": "ApiJobBoardWithTeams",
            "query": _ASHBY_QUERY,
            "variables": {"organizationHostedJobsPageName": org},
        }
        response = self.session.post(ASHBY_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        board = data.get("data", {}).get("jobBoard", {})
        return board.get("jobPostings", [])

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        org = _organization_name(self.company)
        job_id = raw.get("id") or ""
        title = raw.get("title") or ""
        location = raw.get("locationName") or ""
        salary_min, salary_max, salary_period, salary_currency = extract_salary_from_text(
            raw.get("compensationTierSummary")
        )
        posting_url = f"https://jobs.ashbyhq.com/{org}/{job_id}" if org and job_id else ""
        description = raw.get("compensationTierSummary") or ""
        return {
            "external_id": f"as_{job_id}" if job_id else "",
            "title": title,
            "description": description,
            "location": location,
            "work_arrangement": infer_work_arrangement(
                title=title,
                location=location,
                description=description,
                is_remote=(raw.get("workplaceType") or "").lower() == "remote",
            ),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": salary_currency or "USD",
            "salary_period": salary_period,
            "employment_type": (raw.get("employmentType") or "").lower() or None,
            "application_url": posting_url,
            "source": "ashby",
            "source_url": posting_url,
            "posted_date": None,
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
