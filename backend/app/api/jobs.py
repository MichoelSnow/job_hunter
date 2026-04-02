import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobListResponse, JobResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    min_score: float | None = Query(None, ge=0, le=100),
    location: str | None = None,
    is_active: bool = True,
    days: int | None = Query(None, description="Limit to jobs discovered in the last N days"),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List jobs with optional filters. Defaults to active jobs ordered by match score."""
    from datetime import date, timedelta

    query = db.query(Job).filter(Job.is_active == is_active)

    if min_score is not None:
        query = query.filter(Job.overall_match_score >= min_score)
    if location:
        query = query.filter(Job.location.contains(location))
    if days is not None:
        cutoff = date.today() - timedelta(days=days)
        query = query.filter(Job.discovered_date >= cutoff)

    total = query.count()
    items = (
        query.order_by(Job.overall_match_score.desc().nulls_last())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return JobListResponse(total=total, items=items)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    """Get a single job by ID."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/refresh")
def refresh_jobs(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger job discovery and scoring in the background."""
    from app.services.api_aggregator import run_job_discovery

    background_tasks.add_task(run_job_discovery)
    logger.info("Job discovery triggered via API")
    return {"status": "Job discovery started"}


@router.put("/{job_id}/hide")
def hide_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """Mark a job as inactive (hidden from default view)."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    db.commit()
    return {"status": "hidden"}


@router.put("/{job_id}/score")
def rescore_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, str | float]:
    """Recalculate match scores for a single job using the current user profile and criteria."""
    from datetime import datetime

    from app.models.criteria import UserCriteria
    from app.services.scoring_engine import ScoringEngine
    from app.services.text_parser import load_user_profile

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    from app.config.settings import settings as app_settings

    user_profile = load_user_profile()
    engine = ScoringEngine(app_settings, user_profile)

    criteria = [
        {
            "criterion_type": c.criterion_type,
            "criterion_value": c.criterion_value,
            "is_hard_requirement": c.is_hard_requirement,
            "weight": c.weight,
        }
        for c in db.query(UserCriteria).all()
    ]
    required_skills = [
        r.requirement_value
        for r in job.requirements
        if r.requirement_type == "skill" and r.is_required
    ]
    experience_required = next(
        (int(r.requirement_value) for r in job.requirements if r.requirement_type == "experience"),
        None,
    )
    job_dict = {
        "title": job.title,
        "required_skills": required_skills,
        "experience_required": experience_required,
        "salary_min": job.salary_min,
        "company_industry": None,
    }
    u2j, j2u, overall = engine.score(job_dict, criteria)
    job.match_score_user_to_job = u2j
    job.match_score_job_to_user = j2u
    job.overall_match_score = overall
    job.score_calculated_at = datetime.utcnow()
    db.commit()

    return {
        "status": "scored",
        "match_score_user_to_job": u2j,
        "match_score_job_to_user": j2u,
        "overall_match_score": overall,
    }
