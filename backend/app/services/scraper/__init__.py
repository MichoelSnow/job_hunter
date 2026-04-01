from app.services.scraper.base import BaseJobScraper
from app.services.scraper.greenhouse import GreenhouseScraper
from app.services.scraper.html_scraper import HtmlScraper
from app.services.scraper.lever import LeverScraper


def get_scraper(company: dict) -> BaseJobScraper:
    """Return the appropriate scraper for a company based on its ats_type."""
    ats_type = company.get("ats_type", "custom")
    if ats_type == "greenhouse":
        return GreenhouseScraper(company)
    if ats_type == "lever":
        return LeverScraper(company)
    return HtmlScraper(company)


__all__ = [
    "BaseJobScraper",
    "GreenhouseScraper",
    "HtmlScraper",
    "LeverScraper",
    "get_scraper",
]
