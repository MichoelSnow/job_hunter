"""Hard-criteria filtering: removes jobs that don't meet mandatory requirements."""
import logging
import re

logger = logging.getLogger(__name__)

LOCATION_KEYWORDS = ["manhattan", "brooklyn", "new york", "nyc", "ny"]

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
    """Applies hard filters to a list of raw job dicts before DB insertion."""

    def apply_all(self, jobs: list[dict]) -> list[dict]:
        original_count = len(jobs)
        jobs = [j for j in jobs if self._passes_location(j)]
        jobs = [j for j in jobs if self._passes_work_arrangement(j)]
        jobs = [j for j in jobs if self._passes_role_level(j)]
        logger.info(
            "Hard filters: %d → %d jobs (%d removed)",
            original_count,
            len(jobs),
            original_count - len(jobs),
        )
        return jobs

    def _passes_location(self, job: dict) -> bool:
        location = (job.get("location") or "").lower()
        return any(kw in location for kw in LOCATION_KEYWORDS)

    def _passes_work_arrangement(self, job: dict) -> bool:
        """Reject jobs explicitly marked as fully remote."""
        description = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()
        text = f"{title} {description}"
        if any(signal in text for signal in REMOTE_SIGNALS):
            return False
        if job.get("work_arrangement") == "remote":
            return False
        return True

    def _passes_role_level(self, job: dict) -> bool:
        title = (job.get("title") or "").lower()
        return any(re.search(rf"\b{re.escape(kw)}\b", title) for kw in LEADERSHIP_KEYWORDS)
