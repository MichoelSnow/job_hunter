"""HTML scraping fallback for companies without a public ATS JSON API.

`html_selectors` is configured per company in the database/Companies page:

    {
      "job_list": "ul.jobs li",        # selector for each job row
      "title": "a.job-title",          # title element inside each row
      "location": "span.location",     # optional location element
      "url": "a.job-title"             # href source for job URL
    }

`careers_url` is the page to scrape. If selectors are missing, scraper skips.
"""

import logging
from datetime import date
from typing import Any

from app.services.job_normalization import extract_salary_from_text, infer_work_arrangement
from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)


class HtmlScraper(BaseJobScraper):
    """
    Fallback scraper for custom career pages using per-company CSS selectors.
    Configure selectors via the `html_selectors` company field.
    """

    def _fetch_raw(self) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        selectors: dict[str, str] = self.company.get("html_selectors") or {}
        job_list_selector = selectors.get("job_list")

        if not job_list_selector:
            logger.warning(
                "HtmlScraper: no html_selectors.job_list configured for %s — skipping",
                self.company.get("name"),
            )
            return []

        url = self.company.get("careers_url", "")
        if not url:
            logger.warning(
                "HtmlScraper: no careers_url for %s — skipping", self.company.get("name")
            )
            return []

        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        title_sel = selectors.get("title")
        location_sel = selectors.get("location")
        url_sel = selectors.get("url")

        results: list[dict[str, Any]] = []
        for row in soup.select(job_list_selector):
            title_el = row.select_one(title_sel) if title_sel else None
            location_el = row.select_one(location_sel) if location_sel else None
            url_el = row.select_one(url_sel) if url_sel else None

            title = (title_el.get_text(strip=True) if title_el else "").strip()
            location = (location_el.get_text(strip=True) if location_el else "").strip()
            href = (url_el.get("href", "") if url_el else "").strip()

            # Resolve relative URLs
            if href and not href.startswith("http"):
                from urllib.parse import urljoin

                href = urljoin(url, href)

            if not title:
                continue

            results.append(
                {
                    "title": title,
                    "location": location,
                    "url": href,
                    "text": row.get_text(" ", strip=True),
                }
            )

        return results

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        # Generate a stable external_id from company name + title + url since there is
        # no API-provided ID.
        import hashlib

        company_name = self.company.get("name", "")
        id_src = f"{company_name}::{raw.get('title', '')}::{raw.get('url', '')}"
        short_hash = hashlib.md5(id_src.encode()).hexdigest()[:12]

        title = raw.get("title", "")
        location = raw.get("location", "")
        salary_min, salary_max, salary_period, salary_currency = extract_salary_from_text(
            raw.get("text")
        )
        return {
            "external_id": f"html_{short_hash}",
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
            "application_url": raw.get("url", ""),
            "source": "html_scraper",
            "source_url": raw.get("url"),
            "posted_date": None,
            "discovered_date": date.today().isoformat(),
            "company_name": company_name,
            "company_industry": self.company.get("industry"),
            "raw_data": raw,
        }
