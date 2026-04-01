import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.application import Application
from app.models.job import Job
from app.models.tracking import ApiUsageTracking

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)) -> dict:
    """Summary statistics for the jobs dashboard."""
    total_jobs = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar()  # noqa: E712
    scored_jobs = (
        db.query(func.count(Job.id))
        .filter(Job.is_active == True, Job.overall_match_score.is_not(None))  # noqa: E712
        .scalar()
    )
    avg_score = (
        db.query(func.avg(Job.overall_match_score))
        .filter(Job.is_active == True, Job.overall_match_score.is_not(None))  # noqa: E712
        .scalar()
    )
    new_this_week = (
        db.query(func.count(Job.id))
        .filter(Job.discovered_date >= date.today() - timedelta(days=7))
        .scalar()
    )
    total_applications = db.query(func.count(Application.id)).scalar()

    return {
        "total_active_jobs": total_jobs,
        "scored_jobs": scored_jobs,
        "average_match_score": round(avg_score, 1) if avg_score else None,
        "new_jobs_this_week": new_this_week,
        "total_applications": total_applications,
    }


@router.get("/api-usage")
def get_api_usage(db: Session = Depends(get_db)) -> list[dict]:
    """API usage summary for the current month."""
    first_of_month = date.today().replace(day=1)
    rows = (
        db.query(
            ApiUsageTracking.api_name,
            func.sum(ApiUsageTracking.request_count).label("total_requests"),
            func.sum(ApiUsageTracking.cost_estimate).label("total_cost"),
        )
        .filter(ApiUsageTracking.date >= first_of_month)
        .group_by(ApiUsageTracking.api_name)
        .all()
    )
    return [
        {
            "api_name": row.api_name,
            "total_requests": row.total_requests,
            "total_cost": round(row.total_cost or 0, 4),
        }
        for row in rows
    ]
