import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user_settings import UserSettingsResponse, UserSettingsUpdate
from app.services.job_filter import JobFilter, parse_boolean_query, reapply_filters_to_existing_jobs
from app.services.user_settings import get_or_create_user_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/discovery", response_model=UserSettingsResponse)
def get_discovery_settings(db: Session = Depends(get_db)):
    return get_or_create_user_settings(db)


@router.put("/discovery", response_model=UserSettingsResponse)
def update_discovery_settings(payload: UserSettingsUpdate, db: Session = Depends(get_db)):
    try:
        parse_boolean_query(payload.filter_location_query)
        parse_boolean_query(payload.filter_title_query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid boolean query: {exc}") from exc

    settings = get_or_create_user_settings(db)
    settings.search_queries = [q.strip() for q in payload.search_queries if q.strip()]
    settings.search_locations = []
    settings.filter_location_query = payload.filter_location_query.strip()
    settings.filter_title_query = payload.filter_title_query.strip()
    settings.filter_exclude_remote = payload.filter_exclude_remote
    settings.filter_target_salary = payload.filter_target_salary
    settings.filter_include_missing_salary = payload.filter_include_missing_salary
    settings.matching_skills = [skill.strip() for skill in payload.matching_skills if skill.strip()]
    settings.matching_experience_years = payload.matching_experience_years
    settings.matching_current_title = (
        payload.matching_current_title.strip() if payload.matching_current_title else None
    )
    filter_engine = JobFilter(
        allowed_location_query=settings.filter_location_query,
        exclude_remote=settings.filter_exclude_remote,
        title_query=settings.filter_title_query,
        target_salary=settings.filter_target_salary,
        include_missing_salary=settings.filter_include_missing_salary,
    )
    reapply_filters_to_existing_jobs(db, filter_engine)
    db.commit()
    db.refresh(settings)
    return settings
