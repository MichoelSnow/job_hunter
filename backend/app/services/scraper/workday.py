"""Scraper for companies using the Workday ATS (internal JSON API).

Workday exposes a consistent POST endpoint across all tenants:
  https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs

The tenant name, WD instance number (wd1, wd5, etc.), and board name are found
by inspecting the Network tab in browser DevTools on the company's careers page.

Company metadata (in companies table):
  {
    "ats_type": "workday",
    "ats_id": "{tenant}",
    "workday_board": "{board}",
    "workday_instance": "wd5"   // defaults to "wd1" if omitted
  }
"""

import logging
import re
from datetime import date
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from app.services.job_normalization import extract_salary_from_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20
_MYWORKDAY_HOST_RE = re.compile(
    r"^(?P<tenant>[a-z0-9-]+)\.(?P<instance>wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE
)
_CXS_URL_RE = re.compile(
    r"https://(?P<host>[a-z0-9.-]+?\.myworkdayjobs\.com)/wday/cxs/(?P<tenant>[^/]+)/(?P<board>[^/]+)/jobs",
    re.IGNORECASE,
)


class WorkdayScraper(BaseJobScraper):
    """
    Fetches all job postings via the Workday internal jobs API.
    Paginates automatically until all results are retrieved.
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        tenant = (self.company.get("ats_id") or "").strip()
        configured_board = self.company.get("workday_board", "")
        instance = (self.company.get("workday_instance") or "wd1").strip()
        discovered = _discover_workday_endpoint(
            self.session,
            self.company.get("careers_url") or self.company.get("website_url") or "",
        )

        if discovered:
            self._resolved_tenant = discovered["tenant"]
            self._resolved_board = discovered["board"]
            self._resolved_instance = discovered["instance"]
            jobs = self._fetch_board_jobs(
                discovered["base_url"],
                discovered["tenant"],
                discovered["board"],
                discovered["headers"],
            )
            if jobs is not None:
                return jobs

        if not tenant or not configured_board:
            logger.warning(
                "WorkdayScraper: missing ats_id or workday_board for %s — skipping",
                self.company.get("name"),
            )
            return []

        base_url = f"https://{tenant}.{instance}.myworkdayjobs.com"
        headers, inferred_board = self._seed_workday_session(base_url, configured_board)
        board_candidates = _candidate_boards(configured_board, inferred_board)

        for board in board_candidates:
            jobs = self._fetch_board_jobs(base_url, tenant, board, headers)
            if jobs is not None:
                self._resolved_board = board
                self._resolved_tenant = tenant
                self._resolved_instance = instance
                return jobs

        logger.warning(
            "WorkdayScraper: all board candidates failed for %s (configured=%s, inferred=%s)",
            self.company.get("name"),
            configured_board,
            inferred_board,
        )
        return []

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        tenant = getattr(self, "_resolved_tenant", self.company.get("ats_id", ""))
        board = getattr(self, "_resolved_board", self.company.get("workday_board", ""))
        instance = getattr(self, "_resolved_instance", self.company.get("workday_instance", "wd1"))
        external_path = raw.get("externalPath", "")

        apply_url = (
            f"https://{tenant}.{instance}.myworkdayjobs.com/{board}{external_path}"
            if external_path
            else ""
        )

        # bulletFields[0] is the job requisition ID when present
        bullet_fields = raw.get("bulletFields") or []
        req_id = bullet_fields[0] if bullet_fields else ""
        external_id = (
            f"wd_{tenant}_{req_id}" if req_id else f"wd_{tenant}_{external_path.split('_')[-1]}"
        )

        title = raw.get("title") or ""
        location = raw.get("locationsText", "")
        salary_text = " ".join(str(item) for item in bullet_fields if item)
        salary_min, salary_max, salary_period, salary_currency = extract_salary_from_text(
            salary_text
        )
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
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": salary_currency or "USD",
            "salary_period": salary_period,
            "application_url": apply_url,
            "source": "workday",
            "source_url": apply_url,
            "posted_date": None,
            "discovered_date": date.today().isoformat(),
            "company_name": self.company.get("name"),
            "company_industry": self.company.get("industry"),
            "raw_data": raw,
        }

    def _seed_workday_session(
        self, base_url: str, configured_board: str
    ) -> tuple[dict[str, str], str | None]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": base_url,
        }
        seed_url = self.company.get("careers_url") or f"{base_url}/{configured_board}"
        inferred_board: str | None = None

        try:
            landing = self.session.get(seed_url, timeout=15)
            final_url = str(getattr(landing, "url", "") or "")
            inferred_board = _extract_board_from_url(final_url)
            if final_url:
                headers["Referer"] = final_url
        except requests.RequestException as exc:
            logger.warning(
                "WorkdayScraper: failed seeding session for %s: %s", self.company.get("name"), exc
            )

        csrf_token = self.session.cookies.get("CALYPSO_CSRF_TOKEN", "")
        if csrf_token:
            headers["x-calypso-csrf-token"] = csrf_token
        return headers, inferred_board

    def _fetch_board_jobs(
        self,
        base_url: str,
        tenant: str,
        board: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]] | None:
        """Fetch paginated jobs for a single board; return None when board is invalid."""
        url = f"{base_url}/wday/cxs/{tenant}/{board}/jobs"
        all_jobs: list[dict[str, Any]] = []
        offset = 0
        board_success = False

        while True:
            payload = {
                "limit": _PAGE_SIZE,
                "offset": offset,
                "searchText": "",
                "appliedFacets": {},
            }
            response = self.session.post(url, json=payload, headers=headers, timeout=15)

            if response.status_code in (400, 404) and not board_success:
                snippet = (response.text or "").strip().replace("\n", " ")[:220]
                logger.warning(
                    "WorkdayScraper: board candidate failed for %s: board=%s "
                    "url=%s status=%s body=%r",
                    self.company.get("name"),
                    board,
                    url,
                    response.status_code,
                    snippet,
                )
                return None

            response.raise_for_status()
            board_success = True
            data = response.json()

            page = data.get("jobPostings", [])
            all_jobs.extend(page)

            total = data.get("total", 0)
            offset += len(page)
            if offset >= total or not page:
                break

        return all_jobs


def _extract_board_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if "myworkdayjobs.com" not in parsed.netloc:
        return None
    parts = [segment for segment in parsed.path.split("/") if segment]
    if not parts:
        return None

    # Skip locale prefixes like en-US / fr-CA
    if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]):
        parts = parts[1:]
    return parts[0] if parts else None


def _candidate_boards(configured: str, inferred: str | None) -> list[str]:
    candidates: list[str] = []
    for value in (
        configured,
        configured.replace("_", ""),
        inferred,
        (inferred or "").replace("_", ""),
    ):
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def _discover_workday_endpoint(
    session: requests.Session,
    careers_url: str,
) -> dict[str, Any] | None:
    if not careers_url:
        return None

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        landing = session.get(careers_url, timeout=15)
    except requests.RequestException as exc:
        logger.warning("WorkdayScraper: failed careers page discovery for %s: %s", careers_url, exc)
        return None

    final_url = str(getattr(landing, "url", "") or "")
    if final_url:
        headers["Referer"] = final_url
    csrf_token = session.cookies.get("CALYPSO_CSRF_TOKEN", "")
    if csrf_token:
        headers["x-calypso-csrf-token"] = csrf_token

    landing_html = getattr(landing, "text", "") or ""
    if not isinstance(landing_html, str):
        landing_html = str(landing_html)
    endpoint = _extract_endpoint_from_html(landing_html, final_url)
    if not endpoint:
        return None

    base_url, tenant, board, instance = endpoint
    logger.info(
        "WorkdayScraper: discovered endpoint from careers page for %s: "
        "tenant=%s board=%s instance=%s",
        careers_url,
        tenant,
        board,
        instance,
    )
    return {
        "base_url": base_url,
        "tenant": tenant,
        "board": board,
        "instance": instance,
        "headers": headers,
    }


def _extract_endpoint_from_html(html: str, final_url: str) -> tuple[str, str, str, str] | None:
    if not html:
        return None

    for match in _CXS_URL_RE.finditer(html):
        host = match.group("host")
        tenant = unquote(match.group("tenant"))
        board = unquote(match.group("board"))
        parsed_host = _MYWORKDAY_HOST_RE.match(host)
        if not parsed_host:
            continue
        instance = parsed_host.group("instance").lower()
        return (f"https://{host}", tenant, board, instance)

    parsed_final = urlparse(final_url) if final_url else None
    if not parsed_final:
        return None
    host = parsed_final.netloc
    if "myworkdayjobs.com" not in host:
        return None

    relative_match = re.search(r"/wday/cxs/(?P<tenant>[^/]+)/(?P<board>[^/]+)/jobs", html)
    if not relative_match:
        return None

    tenant = unquote(relative_match.group("tenant"))
    board = unquote(relative_match.group("board"))
    host_match = _MYWORKDAY_HOST_RE.match(host)
    if not host_match:
        return None
    instance = host_match.group("instance").lower()
    return (f"https://{host}", tenant, board, instance)
