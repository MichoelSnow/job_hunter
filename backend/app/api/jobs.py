import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobListResponse, JobResponse
from app.services.job_normalization import html_to_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _sanitize_job_response(job: Job) -> JobResponse:
    payload = JobResponse.model_validate(job, from_attributes=True).model_dump()
    payload["description"] = html_to_text(payload.get("description"))
    return JobResponse(**payload)


@router.get("", response_model=JobListResponse)
def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    min_score: float | None = Query(None, ge=0, le=100),
    location: str | None = None,
    is_active: bool | None = Query(True),
    days: int | None = Query(None, description="Limit to jobs discovered in the last N days"),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List jobs with optional filters. Defaults to active jobs ordered by match score."""
    from datetime import date, timedelta

    query = db.query(Job)
    if is_active is not None:
        query = query.filter(Job.is_active == is_active)

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
    return JobListResponse(total=total, items=[_sanitize_job_response(item) for item in items])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    """Get a single job by ID."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _sanitize_job_response(job)


@router.post("/refresh/apis")
def refresh_jobs_api(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger paid API discovery (JSearch + Serply) in the background."""
    from app.services.api_aggregator import discovery_status, run_job_discovery_api_only

    if discovery_status.get("status") == "running":
        return {"status": "already running"}

    background_tasks.add_task(run_job_discovery_api_only)
    logger.info("API-only job discovery triggered via API")
    return {"status": "API job discovery started"}


@router.post("/refresh/scrapers")
def refresh_jobs_scrapers(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger scraper-only discovery in the background."""
    from app.services.api_aggregator import discovery_status, run_job_discovery_scrapers_only

    if discovery_status.get("status") == "running":
        return {"status": "already running"}

    background_tasks.add_task(run_job_discovery_scrapers_only)
    logger.info("Scraper-only job discovery triggered via API")
    return {"status": "Scraper job discovery started"}


@router.get("/refresh/status")
def refresh_status() -> dict:
    """Return the current state of the most recent job discovery run."""
    from app.services.api_aggregator import discovery_status

    return discovery_status


@router.put("/{job_id}/hide")
def hide_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """Mark a job as inactive (hidden from default view)."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    db.commit()
    return {"status": "hidden"}


@router.put("/{job_id}/unhide")
def unhide_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """Mark a previously hidden job as active."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = True
    db.commit()
    return {"status": "active"}


@router.get("/filters/locations")
def list_job_locations(
    is_active: bool | None = Query(True),
    db: Session = Depends(get_db),
) -> list[str]:
    """Return distinct non-empty locations for dropdown filtering."""
    query = db.query(Job.location).filter(Job.location.is_not(None), Job.location != "")
    if is_active is not None:
        query = query.filter(Job.is_active == is_active)
    rows = query.distinct().order_by(Job.location.asc()).all()
    return [row[0] for row in rows]


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
        "company_industry": job.company.industry if job.company else None,
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
