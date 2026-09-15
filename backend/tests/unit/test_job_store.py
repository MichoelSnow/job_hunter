from datetime import date

import app.models  # noqa: F401 — register all models
import pytest
from app.db.base import Base
from app.services.job_store import (
    backfill_missing_salaries,
    backfill_missing_work_arrangements,
    backfill_normalized_locations,
    bulk_upsert_jobs,
    mark_missing_scraped_jobs_closed,
    record_api_usage,
    upsert_company,
    upsert_job,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _job(external_id="js_abc", title="Director of Data", **kwargs):
    return {
        "external_id": external_id,
        "title": title,
        "description": "Join our data team in Manhattan.",
        "location": "Manhattan, NY",
        "work_arrangement": "in_office",
        "application_url": "https://example.com/apply",
        "source": "jsearch_api",
        "discovered_date": "2026-04-01",
        "company_name": "Health Corp",
        **kwargs,
    }


class TestUpsertCompany:
    def test_creates_new_company(self, db):
        company_id = upsert_company(db, "Health Corp")
        db.commit()
        assert company_id is not None

    def test_returns_same_id_on_duplicate(self, db):
        id1 = upsert_company(db, "Health Corp")
        db.commit()
        id2 = upsert_company(db, "Health Corp")
        db.commit()
        assert id1 == id2

    def test_updates_logo_url_if_missing(self, db):
        from app.models.company import Company

        upsert_company(db, "Health Corp", logo_url=None)
        db.commit()
        upsert_company(db, "Health Corp", logo_url="https://example.com/logo.png")
        db.commit()
        company = db.query(Company).filter(Company.name == "Health Corp").first()
        assert company.logo_url == "https://example.com/logo.png"

    def test_sets_industry_on_create(self, db):
        from app.models.company import Company

        upsert_company(db, "Health Corp", industry="healthtech")
        db.commit()
        company = db.query(Company).filter(Company.name == "Health Corp").first()
        assert company.industry == "healthtech"

    def test_sets_industry_if_existing_company_missing_it(self, db):
        from app.models.company import Company

        upsert_company(db, "Health Corp")
        db.commit()
        upsert_company(db, "Health Corp", industry="healthcare")
        db.commit()
        company = db.query(Company).filter(Company.name == "Health Corp").first()
        assert company.industry == "healthcare"


class TestUpsertJob:
    def test_inserts_new_job(self, db):
        _, created = upsert_job(db, _job(), company_id=None)
        db.commit()
        assert created is True

    def test_preserves_raw_and_stores_normalized_location(self, db):
        upsert_job(db, _job(location="New york city"), company_id=None)
        db.commit()
        from app.models.job import Job

        job = db.query(Job).first()
        assert job.location == "NY, NY"
        assert job.location_raw == "New york city"

    def test_uses_remote_for_remote_job_without_location(self, db):
        upsert_job(db, _job(location=None, work_arrangement="remote"), company_id=None)
        db.commit()
        from app.models.job import Job

        job = db.query(Job).first()
        assert job.location == "Remote"
        assert job.location_raw is None

    def test_backfills_normalized_locations(self, db):
        from app.models.job import Job

        db.add(
            Job(
                title="Director of Data",
                description="desc",
                location="New York City, New York",
                application_url="https://example.com/apply",
                source="manual",
                discovered_date=date(2026, 4, 1),
            )
        )
        db.commit()
        assert backfill_normalized_locations(db) == 1
        job = db.query(Job).first()
        assert job.location == "NY, NY"
        assert job.location_raw == "New York City, New York"

    def test_updates_existing_job(self, db):
        upsert_job(db, _job(), company_id=None)
        db.commit()
        _, created = upsert_job(db, _job(title="VP of Data"), company_id=None)
        db.commit()
        assert created is False

    def test_updated_job_reflects_new_title(self, db):
        from app.models.job import Job

        upsert_job(db, _job(), company_id=None)
        db.commit()
        upsert_job(db, _job(title="VP of Data"), company_id=None)
        db.commit()
        job = db.query(Job).filter(Job.external_id == "js_abc").first()
        assert job.title == "VP of Data"

    def test_no_external_id_always_inserts(self, db):
        _, created1 = upsert_job(db, _job(external_id=None), company_id=None)
        db.commit()
        _, created2 = upsert_job(db, _job(external_id=None), company_id=None)
        db.commit()
        assert created1 is True
        assert created2 is True

    def test_existing_closed_job_reopens_when_seen_again(self, db):
        from app.models.job import Job

        upsert_job(db, _job(source="lever", closed_date="2026-04-01"), company_id=None)
        db.commit()
        upsert_job(db, _job(source="lever"), company_id=None)
        db.commit()

        job = db.query(Job).filter(Job.external_id == "js_abc").first()
        assert job is not None
        assert job.closed_date is None


class TestBulkUpsertJobs:
    def test_inserts_multiple_jobs(self, db):
        jobs = [_job("js_1", "Director of Data"), _job("js_2", "VP of Analytics")]
        inserted, updated = bulk_upsert_jobs(db, jobs)
        assert inserted == 2
        assert updated == 0

    def test_deduplicates_on_second_run(self, db):
        jobs = [_job("js_1")]
        bulk_upsert_jobs(db, jobs)
        inserted, updated = bulk_upsert_jobs(db, jobs)
        assert inserted == 0
        assert updated == 1

    def test_creates_company_rows(self, db):
        from app.models.company import Company

        bulk_upsert_jobs(
            db, [_job(company_name="Health Corp"), _job("js_2", company_name="Data Co")]
        )
        count = db.query(Company).count()
        assert count == 2


class TestBackfillMissingSalaries:
    def test_fills_missing_salary_from_description(self, db):
        from app.models.job import Job

        job = _job(
            salary_min=None,
            salary_max=None,
            description="The salary range for this position is: $124,000 - $335,000.",
        )
        upsert_job(db, job, company_id=None)
        db.commit()

        updated = backfill_missing_salaries(db)

        row = db.query(Job).filter(Job.external_id == "js_abc").first()
        assert updated == 1
        assert row is not None
        assert (row.salary_min, row.salary_max, row.salary_period) == (124000, 335000, "year")

    def test_does_not_overwrite_known_salary(self, db):
        from app.models.job import Job

        job = _job(
            salary_min=100000,
            salary_max=150000,
            description="The salary range for this position is: $200,000 - $300,000.",
        )
        upsert_job(db, job, company_id=None)
        db.commit()

        updated = backfill_missing_salaries(db)

        row = db.query(Job).filter(Job.external_id == "js_abc").first()
        assert updated == 0
        assert row is not None
        assert (row.salary_min, row.salary_max) == (100000, 150000)


class TestBackfillMissingWorkArrangements:
    def test_fills_hybrid_arrangement_from_description(self, db):
        from app.models.job import Job

        job = _job(
            work_arrangement="unknown",
            description="Work in the New York office 3 days per week.",
        )
        upsert_job(db, job, company_id=None)
        db.commit()

        updated = backfill_missing_work_arrangements(db)

        row = db.query(Job).filter(Job.external_id == "js_abc").first()
        assert updated == 1
        assert row is not None
        assert row.work_arrangement == "hybrid"


class TestRecordApiUsage:
    def test_inserts_new_row(self, db):
        from app.models.tracking import ApiUsageTracking

        record_api_usage(db, "jsearch_api", 5)
        db.commit()
        row = db.query(ApiUsageTracking).filter(ApiUsageTracking.api_name == "jsearch_api").first()
        assert row.request_count == 5

    def test_increments_existing_row(self, db):
        from app.models.tracking import ApiUsageTracking

        record_api_usage(db, "jsearch_api", 5)
        db.commit()
        record_api_usage(db, "jsearch_api", 3)
        db.commit()
        row = db.query(ApiUsageTracking).filter(ApiUsageTracking.api_name == "jsearch_api").first()
        assert row.request_count == 8


class TestMarkMissingScrapedJobsClosed:
    def test_marks_missing_jobs_closed_for_company_and_source(self, db):
        from app.models.job import Job

        bulk_upsert_jobs(
            db,
            [
                _job(external_id="lv_a", source="lever", company_name="Acme"),
                _job(external_id="lv_b", source="lever", company_name="Acme"),
            ],
        )
        closed = mark_missing_scraped_jobs_closed(
            db,
            observed_external_ids={("Acme", "lever"): {"lv_a"}},
            closed_on=date(2026, 4, 2),
        )
        db.commit()

        assert closed == 1
        a = db.query(Job).filter(Job.external_id == "lv_a").first()
        b = db.query(Job).filter(Job.external_id == "lv_b").first()
        assert a is not None and b is not None
        assert a.closed_date is None
        assert b.closed_date == date(2026, 4, 2)

    def test_empty_observed_set_closes_all_current_jobs(self, db):
        from app.models.job import Job

        bulk_upsert_jobs(
            db,
            [
                _job(external_id="gh_a", source="greenhouse", company_name="Beta"),
                _job(external_id="gh_b", source="greenhouse", company_name="Beta"),
            ],
        )
        closed = mark_missing_scraped_jobs_closed(
            db,
            observed_external_ids={("Beta", "greenhouse"): set()},
            closed_on=date(2026, 4, 2),
        )
        db.commit()

        assert closed == 2
        rows = db.query(Job).filter(Job.source == "greenhouse").all()
        assert all(job.closed_date == date(2026, 4, 2) for job in rows)
