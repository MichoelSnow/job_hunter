"""Upsert logic for persisting normalized job dicts to the database."""
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job, JobRequirement
from app.models.tracking import ApiUsageTracking

logger = logging.getLogger(__name__)

# Fields on Job that should be updated when a job is seen again
_MUTABLE_JOB_FIELDS = (
    "title",
    "description",
    "location",
    "work_arrangement",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "employment_type",
    "posted_date",
    "application_url",
    "source_url",
    "raw_data",
    "is_active",
)


def upsert_company(db: Session, name: str, logo_url: str | None = None) -> int:
    """
    Get or create a Company row by name.
    Updates logo_url if the existing row is missing it.
    Returns the company id.
    """
    company = db.query(Company).filter(Company.name == name).first()
    if company is None:
        company = Company(name=name, logo_url=logo_url)
        db.add(company)
        db.flush()  # populate company.id without committing
        logger.debug("Created company: %s", name)
    elif logo_url and not company.logo_url:
        company.logo_url = logo_url
    return company.id


def upsert_job(db: Session, job_dict: dict[str, Any], company_id: int | None) -> tuple[Job, bool]:
    """
    Insert or update a Job row keyed on external_id.

    Returns (job, created) where created=True means it was a new insertion.
    Jobs with no external_id are always inserted (e.g. manual entries).
    """
    external_id = job_dict.get("external_id")

    existing: Job | None = None
    if external_id:
        existing = db.query(Job).filter(Job.external_id == external_id).first()

    if existing is not None:
        for field in _MUTABLE_JOB_FIELDS:
            value = job_dict.get(field)
            if value is not None:
                setattr(existing, field, value)
        return existing, False

    # Build the Job, excluding keys that don't map to model columns
    job_fields = {
        k: v
        for k, v in job_dict.items()
        if k not in ("company_name", "company_logo") and hasattr(Job, k)
    }
    job_fields["company_id"] = company_id
    if isinstance(job_fields.get("discovered_date"), str):
        job_fields["discovered_date"] = date.fromisoformat(job_fields["discovered_date"])
    if isinstance(job_fields.get("posted_date"), str):
        job_fields["posted_date"] = date.fromisoformat(job_fields["posted_date"])

    job = Job(**job_fields)
    db.add(job)
    return job, True


def record_api_usage(db: Session, api_name: str, request_count: int) -> None:
    """
    Increment (or insert) the daily request count for an API source.
    One row per api_name per calendar day.
    """
    today = date.today()
    row = (
        db.query(ApiUsageTracking)
        .filter(ApiUsageTracking.api_name == api_name, ApiUsageTracking.date == today)
        .first()
    )
    if row is None:
        db.add(ApiUsageTracking(api_name=api_name, request_count=request_count, date=today))
    else:
        row.request_count += request_count


def store_job_requirements(db: Session, job_id: int, parsed: dict[str, Any]) -> None:
    """
    Replace all JobRequirement rows for a job with freshly-parsed results.
    Existing requirements are deleted before new ones are inserted.
    """
    db.query(JobRequirement).filter(JobRequirement.job_id == job_id).delete()

    for skill in parsed.get("required_skills", []):
        db.add(JobRequirement(
            job_id=job_id,
            requirement_type="skill",
            requirement_value=skill,
            is_required=True,
        ))
    for skill in parsed.get("preferred_skills", []):
        db.add(JobRequirement(
            job_id=job_id,
            requirement_type="skill",
            requirement_value=skill,
            is_required=False,
        ))
    years = parsed.get("experience_required")
    if years is not None:
        db.add(JobRequirement(
            job_id=job_id,
            requirement_type="experience",
            requirement_value=str(years),
            is_required=True,
        ))


def parse_and_store_requirements(db: Session, job_dicts: list[dict[str, Any]]) -> None:
    """
    Parse job descriptions and persist requirements for each job.
    Only processes jobs that exist in the DB (matched by external_id or inserted earlier).
    """
    from app.services.text_parser import JobDescriptionParser

    parser = JobDescriptionParser()

    for job_dict in job_dicts:
        external_id = job_dict.get("external_id")
        if not external_id:
            continue
        job = db.query(Job).filter(Job.external_id == external_id).first()
        if job is None:
            continue
        description = job_dict.get("description") or ""
        parsed = parser.parse(description)
        store_job_requirements(db, job.id, parsed)

    db.commit()
    logger.info("Parsed and stored requirements for %d jobs", len(job_dicts))


def bulk_upsert_jobs(
    db: Session, jobs: list[dict[str, Any]]
) -> tuple[int, int]:
    """
    Upsert a list of normalized job dicts.
    Resolves company FK for each job, then upserts the job row.
    Commits once at the end.

    Returns (inserted, updated) counts.
    """
    inserted = 0
    updated = 0

    for job_dict in jobs:
        company_name: str | None = job_dict.get("company_name")
        company_id: int | None = None
        if company_name:
            company_id = upsert_company(
                db, company_name, logo_url=job_dict.get("company_logo")
            )

        _, created = upsert_job(db, job_dict, company_id)
        if created:
            inserted += 1
        else:
            updated += 1

    db.commit()
    logger.info("Upserted %d jobs: %d new, %d updated", inserted + updated, inserted, updated)
    return inserted, updated
