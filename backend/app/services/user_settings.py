import logging

from sqlalchemy.orm import Session

from app.models.user_settings import UserSettings
from app.services.job_filter import LEADERSHIP_KEYWORDS

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_QUERIES = [
    "director OR head OR VP data healthcare OR healthtech New York",
]

DEFAULT_FILTER_LOCATIONS = [
    "New York, NY",
]
DEFAULT_TITLE_KEYWORDS = LEADERSHIP_KEYWORDS


def _quote_term(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _to_or_query(values: list[str]) -> str:
    terms = [_quote_term(v.strip()) for v in values if v and v.strip()]
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    return f"({' OR '.join(terms)})"


DEFAULT_FILTER_LOCATION_QUERY = _to_or_query(DEFAULT_FILTER_LOCATIONS)
DEFAULT_FILTER_TITLE_QUERY = _to_or_query(DEFAULT_TITLE_KEYWORDS)


def get_or_create_user_settings(db: Session) -> UserSettings:
    settings = db.query(UserSettings).order_by(UserSettings.id.asc()).first()
    if settings is not None:
        changed = False
        if settings.filter_location_query is None:
            legacy_locations = getattr(settings, "filter_locations", None) or settings.search_locations
            settings.filter_location_query = _to_or_query(legacy_locations or DEFAULT_FILTER_LOCATIONS)
            changed = True
        if settings.filter_title_query is None:
            legacy_titles = getattr(settings, "filter_title_keywords", None) or DEFAULT_TITLE_KEYWORDS
            settings.filter_title_query = _to_or_query(legacy_titles)
            changed = True
        if settings.search_queries is None:
            settings.search_queries = DEFAULT_SEARCH_QUERIES
            changed = True
        if settings.search_locations is None:
            settings.search_locations = []
            changed = True
        if settings.filter_include_missing_salary is None:
            settings.filter_include_missing_salary = True
            changed = True
        if changed:
            db.commit()
            db.refresh(settings)
        return settings

    settings = UserSettings(
        search_queries=DEFAULT_SEARCH_QUERIES,
        search_locations=[],
        filter_location_query=DEFAULT_FILTER_LOCATION_QUERY,
        filter_title_query=DEFAULT_FILTER_TITLE_QUERY,
        filter_exclude_remote=True,
        filter_target_salary=None,
        filter_include_missing_salary=True,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    logger.info("Created default user discovery settings row")
    return settings
