from app.services.scraper.ashby import AshbyScraper
from app.services.scraper.base import BaseJobScraper
from app.services.scraper.greenhouse import GreenhouseScraper
from app.services.scraper.html_scraper import HtmlScraper
from app.services.scraper.lever import LeverScraper
from app.services.scraper.workday import WorkdayScraper


def get_scraper(company: dict) -> BaseJobScraper:
    """Return the appropriate scraper for a company based on its ats_type."""
    ats_type = company.get("ats_type", "custom")
    if ats_type == "greenhouse":
        return GreenhouseScraper(company)
    if ats_type == "lever":
        return LeverScraper(company)
    if ats_type == "workday":
        return WorkdayScraper(company)
    if ats_type == "ashby":
        return AshbyScraper(company)
    return HtmlScraper(company)


__all__ = [
    "AshbyScraper",
    "BaseJobScraper",
    "GreenhouseScraper",
    "HtmlScraper",
    "LeverScraper",
    "WorkdayScraper",
    "get_scraper",
]
