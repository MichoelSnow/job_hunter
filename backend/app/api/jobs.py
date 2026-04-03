import logging
from html import escape
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job
from app.schemas.job import JobListResponse, JobResponse
from app.services.job_normalization import html_to_text, sanitize_description_html

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _sanitize_job_response(job: Job, *, include_rich_description: bool) -> JobResponse:
    payload = JobResponse.model_validate(job, from_attributes=True).model_dump()
    payload["description"] = html_to_text(payload.get("description"))
    if include_rich_description:
        payload["description_html"] = _extract_description_html(job)
    return JobResponse(**payload)


def _extract_description_html(job: Job) -> str | None:
    raw_data = job.raw_data if isinstance(job.raw_data, dict) else {}
    normalized = sanitize_description_html(raw_data.get("normalized_description_html"))
    if normalized:
        return normalized

    combined = _combine_raw_description_html(raw_data)
    if combined:
        return sanitize_description_html(combined)

    fallback = sanitize_description_html(job.description)
    return fallback or None


def _combine_raw_description_html(raw_data: dict) -> str:
    blocks: list[str] = []

    for key in (
        "content",
        "description",
        "descriptionHtml",
        "description_html",
        "job_description",
        "additional",
        "opening",
    ):
        value = raw_data.get(key)
        if value:
            blocks.append(str(value))

    lists = raw_data.get("lists")
    if isinstance(lists, list):
        for section in lists:
            if not isinstance(section, dict):
                continue
            heading = html_to_text(section.get("text"))
            content = section.get("content")
            if heading:
                blocks.append(f"<h3>{escape(heading)}</h3>")
            if content:
                blocks.append(f"<ul>{content}</ul>")

    return "\n".join(blocks).strip()


def _apply_job_sorting(
    query,
    *,
    sort_by: str | None,
    sort_direction: Literal["asc", "desc"],
):
    if not sort_by:
        return query.order_by(Job.overall_match_score.desc().nulls_last(), Job.id.desc())

    sortable_columns = {
        "title": Job.title,
        "location": Job.location,
        "work_arrangement": Job.work_arrangement,
        "source": Job.source,
        "posted_date": Job.posted_date,
        "closed_date": Job.closed_date,
        "discovered_date": Job.discovered_date,
        "overall_match_score": Job.overall_match_score,
        "salary": func.coalesce(Job.salary_max, Job.salary_min),
    }

    if sort_by == "company_name":
        query = query.outerjoin(Company, Job.company_id == Company.id)
        sort_expr = Company.name
    else:
        sort_expr = sortable_columns.get(sort_by)

    if sort_expr is None:
        return query.order_by(Job.overall_match_score.desc().nulls_last(), Job.id.desc())

    ordered = asc(sort_expr) if sort_direction == "asc" else desc(sort_expr)
    return query.order_by(ordered.nulls_last(), Job.id.desc())


@router.get("", response_model=JobListResponse)
def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    min_score: float | None = Query(None, ge=0, le=100),
    location: str | None = None,
    is_active: bool | None = Query(True),
    days: int | None = Query(None, description="Limit to jobs discovered in the last N days"),
    sort_by: str | None = Query(
        None,
        pattern="^(title|company_name|location|work_arrangement|salary|source|posted_date|closed_date|discovered_date|overall_match_score)$",
    ),
    sort_direction: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List jobs with optional filters. Defaults to active jobs ordered by match score."""
    from datetime import date, timedelta

    query = db.query(Job)
    query = query.filter(Job.passes_user_filters == True)  # noqa: E712
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
    sorted_query = _apply_job_sorting(
        query,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    items = sorted_query.offset(skip).limit(limit).all()
    return JobListResponse(
        total=total,
        items=[_sanitize_job_response(item, include_rich_description=False) for item in items],
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    """Get a single job by ID."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _sanitize_job_response(job, include_rich_description=True)


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


@router.get("/refresh/scrapers/targets")
def refresh_scrapers_targets() -> dict:
    """Preview which companies are eligible for scraper refresh and which are skipped."""
    from app.services.api_aggregator import get_scrape_targets

    enabled, skipped = get_scrape_targets()
    return {
        "enabled_count": len(enabled),
        "enabled": [company.get("name") for company in enabled],
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


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
