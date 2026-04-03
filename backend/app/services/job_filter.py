"""Hard-criteria filtering: removes jobs that don't meet mandatory requirements."""
import logging
import re

from sqlalchemy.orm import Session

from app.models.job import Job

logger = logging.getLogger(__name__)

REMOTE_SIGNALS = ["fully remote", "100% remote", "remote only", "work from home"]

LEADERSHIP_KEYWORDS = [
    "director",
    "vp",
    "vice president",
    "head of",
    "chief",
    "lead",
    "manager",
    "principal",
]


class JobFilter:
    """Applies user-configured hard filters to jobs."""

    def __init__(
        self,
        *,
        allowed_locations: list[str] | None = None,
        exclude_remote: bool = True,
        title_keywords: list[str] | None = None,
        target_salary: int | None = None,
        include_missing_salary: bool = True,
    ) -> None:
        self.exclude_remote = exclude_remote
        self.title_keywords = [k.strip().lower() for k in (title_keywords or []) if k and k.strip()]
        self.location_keywords = _location_keywords_from_search_locations(allowed_locations or [])
        self.target_salary = target_salary
        self.include_missing_salary = include_missing_salary

    def apply_all(self, jobs: list[dict]) -> list[dict]:
        original_count = len(jobs)
        jobs = [j for j in jobs if self.passes(j)]
        logger.info(
            "Hard filters: %d → %d jobs (%d removed)",
            original_count,
            len(jobs),
            original_count - len(jobs),
        )
        return jobs

    def passes(self, job: dict) -> bool:
        return (
            self._passes_location(job)
            and self._passes_work_arrangement(job)
            and self._passes_role_level(job)
            and self._passes_salary(job)
        )

    def _passes_location(self, job: dict) -> bool:
        if not self.location_keywords:
            return True
        location = (job.get("location") or "").lower()
        return any(kw in location for kw in self.location_keywords)

    def _passes_work_arrangement(self, job: dict) -> bool:
        """Reject jobs explicitly marked as fully remote."""
        if not self.exclude_remote:
            return True
        description = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()
        text = f"{title} {description}"
        if any(signal in text for signal in REMOTE_SIGNALS):
            return False
        if job.get("work_arrangement") == "remote":
            return False
        return True

    def _passes_role_level(self, job: dict) -> bool:
        if not self.title_keywords:
            return True
        title = (job.get("title") or "").lower()
        return any(re.search(rf"\b{re.escape(kw)}\b", title) for kw in self.title_keywords)

    def _passes_salary(self, job: dict) -> bool:
        if self.target_salary is None:
            return True

        salary_min = _to_int(job.get("salary_min"))
        salary_max = _to_int(job.get("salary_max"))

        if salary_min is None and salary_max is None:
            return self.include_missing_salary

        if salary_min is not None and salary_max is not None:
            high = max(salary_min, salary_max)
            # Minimum salary threshold: keep jobs that can meet/exceed target.
            return high >= self.target_salary

        if salary_min is not None:
            return salary_min >= self.target_salary

        if salary_max is not None:
            return salary_max >= self.target_salary

        return self.include_missing_salary


def _location_keywords_from_search_locations(search_locations: list[str]) -> list[str]:
    keywords: set[str] = set()

    for value in search_locations:
        normalized = (value or "").strip().lower()
        if not normalized:
            continue
        # Whole phrase and comma-separated parts (e.g. "New York, NY")
        keywords.add(normalized)
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        for part in parts:
            keywords.add(part)
            tokens = [t for t in re.split(r"[\s/]+", part) if t]
            if len(tokens) > 1:
                keywords.add(" ".join(tokens))

        if "new york" in normalized:
            keywords.update({"new york", "nyc", "manhattan", "brooklyn", "queens", "bronx"})

    return sorted(keywords)


def reapply_filters_to_existing_jobs(db: Session, filter_engine: JobFilter) -> int:
    """Recompute passes_user_filters for all jobs in DB using current settings."""
    rows = db.query(Job).all()
    changed = 0
    for row in rows:
        job_dict = {
            "title": row.title,
            "description": row.description,
            "location": row.location,
            "work_arrangement": row.work_arrangement,
            "salary_min": row.salary_min,
            "salary_max": row.salary_max,
        }
        visible = filter_engine.passes(job_dict)
        if row.passes_user_filters != visible:
            row.passes_user_filters = visible
            changed += 1
    if changed:
        logger.info("Reapplied user filters to jobs: %d rows changed", changed)
    return changed


def _to_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
