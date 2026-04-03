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


def get_or_create_user_settings(db: Session) -> UserSettings:
    settings = db.query(UserSettings).order_by(UserSettings.id.asc()).first()
    if settings is not None:
        changed = False
        if settings.filter_locations is None:
            settings.filter_locations = settings.search_locations or DEFAULT_FILTER_LOCATIONS
            changed = True
        if settings.filter_title_keywords is None:
            settings.filter_title_keywords = DEFAULT_TITLE_KEYWORDS
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
        filter_locations=DEFAULT_FILTER_LOCATIONS,
        filter_title_keywords=DEFAULT_TITLE_KEYWORDS,
        filter_exclude_remote=True,
        filter_target_salary=None,
        filter_include_missing_salary=True,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    logger.info("Created default user discovery settings row")
    return settings
