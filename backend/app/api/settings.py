import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user_settings import UserSettingsResponse, UserSettingsUpdate
from app.services.job_filter import JobFilter, reapply_filters_to_existing_jobs
from app.services.user_settings import get_or_create_user_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/discovery", response_model=UserSettingsResponse)
def get_discovery_settings(db: Session = Depends(get_db)):
    return get_or_create_user_settings(db)


@router.put("/discovery", response_model=UserSettingsResponse)
def update_discovery_settings(payload: UserSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_user_settings(db)
    settings.search_queries = [q.strip() for q in payload.search_queries if q.strip()]
    settings.search_locations = []
    settings.filter_locations = [loc.strip() for loc in payload.filter_locations if loc.strip()]
    settings.filter_title_keywords = [
        keyword.strip() for keyword in payload.filter_title_keywords if keyword.strip()
    ]
    settings.filter_exclude_remote = payload.filter_exclude_remote
    settings.filter_target_salary = payload.filter_target_salary
    settings.filter_include_missing_salary = payload.filter_include_missing_salary
    filter_engine = JobFilter(
        allowed_locations=settings.filter_locations,
        exclude_remote=settings.filter_exclude_remote,
        title_keywords=settings.filter_title_keywords,
        target_salary=settings.filter_target_salary,
        include_missing_salary=settings.filter_include_missing_salary,
    )
    reapply_filters_to_existing_jobs(db, filter_engine)
    db.commit()
    db.refresh(settings)
    return settings
