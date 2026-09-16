"""Upsert logic for persisting normalized job dicts to the database."""

import hashlib
import logging
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job, JobLocation, JobRequirement
from app.models.tracking import ApiUsageTracking
from app.services.job_normalization import (
    extract_salary_from_text,
    html_to_text,
    infer_work_arrangement,
    normalize_location,
    parse_locations,
)

logger = logging.getLogger(__name__)
_JOB_COLUMN_KEYS = set(Job.__table__.columns.keys())

# Fields on Job that should be updated when a job is seen again
_MUTABLE_JOB_FIELDS = (
    "title",
    "description",
    "location",
    "location_raw",
    "work_arrangement",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "employment_type",
    "posted_date",
    "closed_date",
    "application_url",
    "source_url",
    "raw_data",
    "is_active",
    "passes_user_filters",
)
_COMPANY_API_SOURCES = {"ashby", "greenhouse", "lever", "workday"}


def upsert_company(
    db: Session,
    name: str,
    logo_url: str | None = None,
    industry: str | None = None,
) -> int:
    """
    Get or create a Company row by name.
    Updates logo_url if the existing row is missing it.
    Returns the company id.
    """
    company = db.query(Company).filter(Company.name == name).first()
    if company is None:
        company = Company(name=name, logo_url=logo_url, industry=industry)
        db.add(company)
        db.flush()  # populate company.id without committing
        logger.debug("Created company: %s", name)
    elif logo_url and not company.logo_url:
        company.logo_url = logo_url
    if industry and not company.industry:
        company.industry = industry
    return company.id


def upsert_job(db: Session, job_dict: dict[str, Any], company_id: int | None) -> tuple[Job, bool]:
    """
    Insert or update a Job row keyed on external_id.

    Returns (job, created) where created=True means it was a new insertion.
    Jobs with no external_id are always inserted (e.g. manual entries).
    """
    job_dict = dict(job_dict)
    raw_location = job_dict.get("location_raw") or job_dict.get("location")
    job_dict["location_raw"] = raw_location
    normalized_location = normalize_location(raw_location)
    if not normalized_location and (job_dict.get("work_arrangement") or "").casefold() == "remote":
        normalized_location = "Remote"
    job_dict["location"] = normalized_location
    external_id = job_dict.get("external_id")

    existing = _find_existing_job(db, job_dict)
    if existing is not None and existing.description != job_dict.get("description"):
        versioned_external_id = _versioned_external_id(job_dict)
        job_dict["external_id"] = versioned_external_id
        existing = db.query(Job).filter(Job.external_id == versioned_external_id).first()

    if existing is not None:
        if source_priority(job_dict.get("source")) > source_priority(existing.source):
            existing.source = job_dict.get("source")
            incoming_external_id = job_dict.get("external_id")
            if incoming_external_id:
                external_id_owner = (
                    db.query(Job).filter(Job.external_id == incoming_external_id).first()
                )
                if external_id_owner is None or external_id_owner.id == existing.id:
                    existing.external_id = incoming_external_id
        for field in _MUTABLE_JOB_FIELDS:
            value = job_dict.get(field)
            if field == "closed_date":
                if isinstance(value, str):
                    value = date.fromisoformat(value)
                # closed_date is explicitly cleared when a reopened role is observed.
                setattr(existing, field, value)
                continue
            if value is not None:
                if field in ("posted_date",) and isinstance(value, str):
                    value = date.fromisoformat(value)
                setattr(existing, field, value)
        _replace_job_locations(db, existing)
        return existing, False

    # Build the Job, excluding keys that don't map to model columns
    job_fields = {
        k: v
        for k, v in job_dict.items()
        if k not in ("company_name", "company_logo", "company_industry") and k in _JOB_COLUMN_KEYS
    }
    job_fields["company_id"] = company_id
    if isinstance(job_fields.get("discovered_date"), str):
        job_fields["discovered_date"] = date.fromisoformat(job_fields["discovered_date"])
    if isinstance(job_fields.get("posted_date"), str):
        job_fields["posted_date"] = date.fromisoformat(job_fields["posted_date"])
    if isinstance(job_fields.get("closed_date"), str):
        job_fields["closed_date"] = date.fromisoformat(job_fields["closed_date"])

    job = Job(**job_fields)
    db.add(job)
    db.flush()
    _replace_job_locations(db, job)
    return job, True


def _find_existing_job(db: Session, job_dict: dict[str, Any]) -> Job | None:
    """Find an exact snapshot match, then fall back to the provider identifier."""
    application_url = normalize_application_url(job_dict.get("application_url"))
    description = job_dict.get("description")
    if application_url and description is not None:
        existing_candidates = (
            db.query(Job)
            .filter(
                func.lower(func.rtrim(Job.application_url, "/")) == application_url.casefold(),
                Job.description == description,
            )
            .all()
        )
        if existing_candidates:
            return min(
                existing_candidates,
                key=lambda job: (-source_priority(job.source), job.discovered_date, job.id),
            )

    external_id = job_dict.get("external_id")
    if external_id:
        return db.query(Job).filter(Job.external_id == external_id).first()
    return None


def normalize_application_url(value: Any) -> str:
    """Normalize the small set of URL differences that commonly create duplicates."""
    return str(value or "").strip().rstrip("/")


def source_priority(source: Any) -> int:
    """Prefer known company ATS/API sources over aggregator sources."""
    return int(str(source or "").casefold() in _COMPANY_API_SOURCES)


def _versioned_external_id(job_dict: dict[str, Any]) -> str | None:
    """Create a stable provider-ID variant for a changed description snapshot."""
    external_id = job_dict.get("external_id")
    if not external_id:
        return None
    fingerprint = "|".join(
        (
            str(external_id),
            normalize_application_url(job_dict.get("application_url")),
            str(job_dict.get("description") or ""),
        )
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"{external_id}:snapshot:{digest}"


def _replace_job_locations(db: Session, job: Job) -> None:
    """Replace structured location records for a job from its preserved source value."""
    db.query(JobLocation).filter(JobLocation.job_id == job.id).delete()
    for location in parse_locations(job.location_raw):
        db.add(JobLocation(job_id=job.id, **location))


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
        db.add(
            JobRequirement(
                job_id=job_id,
                requirement_type="skill",
                requirement_value=skill,
                is_required=True,
            )
        )
    for skill in parsed.get("preferred_skills", []):
        db.add(
            JobRequirement(
                job_id=job_id,
                requirement_type="skill",
                requirement_value=skill,
                is_required=False,
            )
        )
    years = parsed.get("experience_required")
    if years is not None:
        db.add(
            JobRequirement(
                job_id=job_id,
                requirement_type="experience",
                requirement_value=str(years),
                is_required=True,
            )
        )


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


def bulk_upsert_jobs(db: Session, jobs: list[dict[str, Any]]) -> tuple[int, int]:
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
                db,
                company_name,
                logo_url=job_dict.get("company_logo"),
                industry=job_dict.get("company_industry"),
            )

        _, created = upsert_job(db, job_dict, company_id)
        if created:
            inserted += 1
        else:
            updated += 1

    db.commit()
    logger.info("Upserted %d jobs: %d new, %d updated", inserted + updated, inserted, updated)
    return inserted, updated


def backfill_missing_salaries(db: Session) -> int:
    """Fill missing salary fields from descriptions already stored in the database."""
    updated = 0
    jobs = db.query(Job).filter((Job.salary_min.is_(None)) | (Job.salary_max.is_(None))).all()

    for job in jobs:
        stored_text = _stored_job_text(job)
        salary_min, salary_max, salary_period, salary_currency = extract_salary_from_text(
            stored_text
        )
        if salary_min is None and salary_max is None:
            continue

        changed = False
        if job.salary_min is None and salary_min is not None:
            job.salary_min = salary_min
            changed = True
        if job.salary_max is None and salary_max is not None:
            job.salary_max = salary_max
            changed = True
        if changed and not job.salary_period and salary_period:
            job.salary_period = salary_period
        if changed and not job.salary_currency and salary_currency:
            job.salary_currency = salary_currency
        if changed:
            updated += 1

    db.commit()
    logger.info("Backfilled salaries for %d historic jobs", updated)
    return updated


def _stored_job_text(job: Job) -> str:
    values: list[str] = [job.description or ""]
    raw_data = job.raw_data if isinstance(job.raw_data, dict) else {}
    for key in (
        "job_description",
        "description",
        "descriptionPlain",
        "descriptionBodyPlain",
        "descriptionHtml",
        "content",
        "additionalPlain",
        "openingPlain",
    ):
        value = raw_data.get(key)
        if value:
            values.append(html_to_text(str(value)))
    return " ".join(value for value in values if value)


def backfill_missing_work_arrangements(db: Session) -> int:
    """Fill unknown work arrangements from descriptions already stored in the database."""
    updated = 0
    jobs = (
        db.query(Job)
        .filter((Job.work_arrangement.is_(None)) | (Job.work_arrangement == "unknown"))
        .all()
    )

    for job in jobs:
        arrangement = infer_work_arrangement(
            title=job.title,
            location=job.location,
            description=_stored_job_text(job),
        )
        if arrangement == "unknown":
            continue
        job.work_arrangement = arrangement
        updated += 1

    db.commit()
    logger.info("Backfilled work arrangements for %d historic jobs", updated)
    return updated


def backfill_normalized_locations(db: Session, *, commit: bool = True) -> int:
    """Normalize locations already stored before structured location support."""
    updated = 0
    for job in db.query(Job).all():
        raw_location = job.location_raw or job.location
        old_location = job.location
        normalized = normalize_location(raw_location)
        changed = job.location_raw != raw_location or job.location != normalized
        if changed:
            job.location_raw = raw_location
            job.location = normalized
        if old_location != normalized or not job.locations:
            _replace_job_locations(db, job)
            changed = True
        if changed:
            updated += 1

    if updated and commit:
        db.commit()
    logger.info("Normalized locations for %d historic jobs", updated)
    return updated


def mark_missing_scraped_jobs_closed(
    db: Session,
    observed_external_ids: dict[tuple[str, str], set[str]],
    closed_on: date,
) -> int:
    """
    Mark scraped jobs as closed when they disappear from a successful scraper run.

    observed_external_ids is keyed by (company_name, source), with values as the set
    of currently observed external_ids for that company/source in the current run.
    """
    from app.models.company import Company

    closed_count = 0
    for (company_name, source), seen_ids in observed_external_ids.items():
        query = (
            db.query(Job)
            .join(Company, Job.company_id == Company.id)
            .filter(
                Company.name == company_name,
                Job.source == source,
                Job.closed_date.is_(None),
            )
        )
        if seen_ids:
            query = query.filter(~Job.external_id.in_(seen_ids))

        stale_jobs = query.all()
        for job in stale_jobs:
            job.closed_date = closed_on
        closed_count += len(stale_jobs)

    if closed_count:
        logger.info("Marked %d scraped jobs as closed on %s", closed_count, closed_on.isoformat())
    return closed_count
