"""Report or remove duplicate job snapshots from the local database."""

import argparse
import logging
import logging.handlers
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from re import sub

from app.db.session import SessionLocal
from app.models.application import Application
from app.models.job import Job
from app.services.job_normalization import html_to_text
from app.services.job_store import normalize_application_url, source_priority

logger = logging.getLogger(__name__)
_LOG_FILE = Path(__file__).parents[2] / "logs" / "cleanup_duplicate_jobs.log"
_SIMILARITY_THRESHOLD = 0.99


def find_duplicate_groups(jobs: list[Job]) -> list[list[Job]]:
    """Group duplicate job snapshots across sources using stable content signals."""
    parents = list(range(len(jobs)))
    matching_job: dict[tuple[str, ...], int] = {}
    content_jobs: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        first_root = find(first)
        second_root = find(second)
        if first_root != second_root:
            parents[second_root] = first_root

    for index, job in enumerate(jobs):
        application_url = normalize_application_url(job.application_url)
        description = _normalize_description(job.description)
        keys: list[tuple[str, ...]] = []
        if application_url and description:
            keys.append(("url", application_url.casefold(), description))

        company = _normalize_text(job.company_name)
        title = _normalize_text(job.title)
        if company and title and description:
            keys.append(("content", company, title, description))
            content_jobs[(company, title)].setdefault(description, index)

        for key in keys:
            previous_index = matching_job.get(key)
            if previous_index is None:
                matching_job[key] = index
            else:
                union(index, previous_index)

    for matching_jobs in content_jobs.values():
        unique_descriptions = list(matching_jobs.items())
        for first_position, (first_description, first_index) in enumerate(unique_descriptions):
            for second_description, second_index in unique_descriptions[first_position + 1 :]:
                if not _descriptions_may_match(first_description, second_description):
                    continue
                union(first_index, second_index)

    duplicate_groups: dict[int, list[Job]] = defaultdict(list)
    for index, job in enumerate(jobs):
        duplicate_groups[find(index)].append(job)

    return [
        sorted(group, key=lambda job: (-source_priority(job.source), job.discovered_date, job.id))
        for group in duplicate_groups.values()
        if len(group) > 1
    ]


def _normalize_text(value: str | None) -> str:
    return sub(r"\s+", " ", str(value or "")).strip().casefold()


def _normalize_description(value: str | None) -> str:
    description = _normalize_text(html_to_text(value))
    for bullet in ("•", "‣", "▪", "◦", "·"):
        description = description.replace(bullet, "-")
    return description


def _descriptions_may_match(first: str, second: str) -> bool:
    """Return whether descriptions pass inexpensive checks before full comparison."""
    shorter, longer = sorted((len(first), len(second)))
    if not longer or shorter / longer < _SIMILARITY_THRESHOLD:
        return False

    matcher = SequenceMatcher(None, first, second)
    return (
        matcher.real_quick_ratio() >= _SIMILARITY_THRESHOLD
        and matcher.quick_ratio() >= _SIMILARITY_THRESHOLD
        and matcher.ratio() >= _SIMILARITY_THRESHOLD
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report or remove duplicate job snapshots while preserving history."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete later duplicates. Without this flag, only report candidates.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(Job.id.asc()).all()
        duplicate_groups = find_duplicate_groups(jobs)
        application_job_ids = {job_id for (job_id,) in db.query(Application.job_id).all()}

        removable_rows = 0
        skipped_groups = 0
        for group in duplicate_groups:
            survivor = group[0]
            duplicate_rows = group[1:]
            if any(job.id in application_job_ids for job in group):
                skipped_groups += 1
                logger.warning(
                    "Skipping duplicate group with application: candidates=%s",
                    ", ".join(str(job.id) for job in group),
                )
                continue

            removable_rows += len(duplicate_rows)
            action = "Removing" if args.apply else "Would remove"
            logger.info(
                "%s jobs %s; keeping preferred job %s discovered %s",
                action,
                ", ".join(str(job.id) for job in duplicate_rows),
                survivor.id,
                survivor.discovered_date,
            )
            if args.apply:
                for job in duplicate_rows:
                    db.delete(job)

        if args.apply:
            db.commit()
            logger.info(
                "Duplicate cleanup complete: removed %d rows; skipped %d groups with applications",
                removable_rows,
                skipped_groups,
            )
        else:
            db.rollback()
            logger.info(
                "Dry run complete: %d rows would be removed; skipped %d groups with applications",
                removable_rows,
                skipped_groups,
            )
    except Exception:
        db.rollback()
        logger.exception("Duplicate cleanup failed")
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    _LOG_FILE.parent.mkdir(exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler])
    raise SystemExit(main())
