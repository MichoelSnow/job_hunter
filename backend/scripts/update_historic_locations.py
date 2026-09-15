"""Normalize location values for jobs already stored in the local database."""

import argparse
import logging

from app.db.session import SessionLocal, create_tables
from app.services.job_store import backfill_normalized_locations

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize historic job locations and preserve their source values."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report rows that would change without committing updates.",
    )
    args = parser.parse_args()

    create_tables()
    db = SessionLocal()
    try:
        updated = backfill_normalized_locations(db, commit=not args.dry_run)
        if args.dry_run:
            db.rollback()
            logger.info("Dry run complete: %d historic jobs would be updated", updated)
        else:
            logger.info("Location update complete: %d historic jobs updated", updated)
    except Exception:
        db.rollback()
        logger.exception("Historic location update failed")
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
