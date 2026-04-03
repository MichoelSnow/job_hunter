"""Synchronize Company rows with metadata from config/companies.json."""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company

logger = logging.getLogger(__name__)
_COMPANIES_CONFIG_PATH = Path(__file__).parents[3] / "config" / "companies.json"


def enrich_companies_from_config(db: Session) -> int:
    """
    Ensure config companies exist in DB and enrich metadata for all matching rows.
    Existing values are only filled when missing; explicit DB values are preserved.
    Returns number of inserted + updated rows.
    """
    config_map = _load_companies_config()
    if not config_map:
        return 0

    inserted = 0
    updated = 0
    existing_by_name = {company.name: company for company in db.query(Company).all()}

    for name, config in config_map.items():
        company = existing_by_name.get(name)
        if company is None:
            careers_url = config.get("careers_url")
            company = Company(
                name=name,
                industry=config.get("industry"),
                ats_type=config.get("ats_type"),
                ats_id=config.get("ats_id"),
                careers_page_url=careers_url,
                website_url=careers_url,
                is_priority=bool(config.get("is_priority")),
            )
            db.add(company)
            existing_by_name[name] = company
            inserted += 1
            continue

        changed = False
        if not company.industry and config.get("industry"):
            company.industry = config["industry"]
            changed = True
        if not company.ats_type and config.get("ats_type"):
            company.ats_type = config["ats_type"]
            changed = True
        if not company.ats_id and config.get("ats_id"):
            company.ats_id = config["ats_id"]
            changed = True

        careers_url = config.get("careers_url")
        if not company.careers_page_url and careers_url:
            company.careers_page_url = careers_url
            changed = True
        if not company.website_url and careers_url:
            company.website_url = careers_url
            changed = True

        if config.get("is_priority") and not company.is_priority:
            company.is_priority = True
            changed = True

        if changed:
            updated += 1

    total_changes = inserted + updated
    if total_changes:
        db.commit()
        logger.info(
            "Synced companies from config: %d inserted, %d updated",
            inserted,
            updated,
        )
    return total_changes


def _load_companies_config() -> dict[str, dict[str, Any]]:
    if not _COMPANIES_CONFIG_PATH.exists():
        logger.warning("companies.json not found at %s", _COMPANIES_CONFIG_PATH)
        return {}
    with _COMPANIES_CONFIG_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    companies = data.get("companies", [])
    return {
        c.get("name"): c
        for c in companies
        if isinstance(c, dict) and c.get("name")
    }
