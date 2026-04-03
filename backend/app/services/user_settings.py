import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.user_settings import UserSettings
from app.services.job_filter import LEADERSHIP_KEYWORDS
from app.services.text_parser import ResumeParser, load_user_profile

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).parents[3]

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


def _initial_matching_profile() -> tuple[list[str], int | None, str | None, str | None, float | None]:
    profile = load_user_profile()
    resume_path_rel = (profile.get("user") or {}).get("resume_file_path")
    current_title = profile.get("current_title")
    if not resume_path_rel:
        return [], profile.get("experience_years"), current_title, None, None

    resume_path = (_REPO_ROOT / resume_path_rel).resolve()
    if not resume_path.exists():
        return [], profile.get("experience_years"), current_title, None, None

    try:
        parsed = ResumeParser().parse_file(str(resume_path))
    except Exception as exc:
        logger.warning("Failed to parse resume at %s while creating defaults: %s", resume_path, exc)
        return [], profile.get("experience_years"), current_title, None, None

    parsed_titles = parsed.get("titles") or []
    return (
        [str(s).strip() for s in (parsed.get("skills") or []) if str(s).strip()],
        parsed.get("experience_years"),
        current_title or parsed.get("current_title") or (parsed_titles[0] if parsed_titles else None),
        str(Path(resume_path_rel)),
        resume_path.stat().st_mtime,
    )


def _sync_matching_profile_from_saved_resume(settings: UserSettings) -> bool:
    """Refresh matching profile when the saved resume path has changed on disk."""
    profile = load_user_profile()
    resume_path_rel = settings.matching_resume_path or (profile.get("user") or {}).get("resume_file_path")
    if not resume_path_rel:
        return False

    resume_path = (_REPO_ROOT / resume_path_rel).resolve()
    if not resume_path.exists():
        return False

    mtime = resume_path.stat().st_mtime
    if (
        settings.matching_resume_path == str(Path(resume_path_rel))
        and settings.matching_resume_mtime is not None
        and abs(settings.matching_resume_mtime - mtime) < 1e-6
    ):
        return False

    try:
        parsed = ResumeParser().parse_file(str(resume_path))
    except Exception as exc:
        logger.warning("Failed to parse resume at %s while syncing settings: %s", resume_path, exc)
        return False

    parsed_titles = parsed.get("titles") or []
    settings.matching_skills = [str(s).strip() for s in (parsed.get("skills") or []) if str(s).strip()]
    settings.matching_experience_years = parsed.get("experience_years")
    settings.matching_current_title = parsed.get("current_title") or (parsed_titles[0] if parsed_titles else None)
    settings.matching_resume_path = str(Path(resume_path_rel))
    settings.matching_resume_mtime = mtime
    return True


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
        if settings.matching_skills is None:
            skills, experience_years, current_title, resume_path, resume_mtime = _initial_matching_profile()
            settings.matching_skills = skills
            if settings.matching_experience_years is None:
                settings.matching_experience_years = experience_years
            if settings.matching_current_title is None:
                settings.matching_current_title = current_title
            if resume_path and settings.matching_resume_path is None:
                settings.matching_resume_path = resume_path
            if resume_mtime is not None and settings.matching_resume_mtime is None:
                settings.matching_resume_mtime = resume_mtime
            changed = True
        if settings.matching_experience_years is None and settings.matching_current_title is None and not settings.matching_skills:
            skills, experience_years, current_title, resume_path, resume_mtime = _initial_matching_profile()
            settings.matching_skills = skills
            settings.matching_experience_years = experience_years
            settings.matching_current_title = current_title
            settings.matching_resume_path = resume_path
            settings.matching_resume_mtime = resume_mtime
            changed = True
        if _sync_matching_profile_from_saved_resume(settings):
            changed = True
        if changed:
            db.commit()
            db.refresh(settings)
        return settings

    skills, experience_years, current_title, resume_path, resume_mtime = _initial_matching_profile()
    settings = UserSettings(
        search_queries=DEFAULT_SEARCH_QUERIES,
        search_locations=[],
        filter_location_query=DEFAULT_FILTER_LOCATION_QUERY,
        filter_title_query=DEFAULT_FILTER_TITLE_QUERY,
        filter_exclude_remote=True,
        filter_target_salary=None,
        filter_include_missing_salary=True,
        matching_skills=skills,
        matching_experience_years=experience_years,
        matching_current_title=current_title,
        matching_resume_path=resume_path,
        matching_resume_mtime=resume_mtime,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    logger.info("Created default user discovery settings row")
    return settings
