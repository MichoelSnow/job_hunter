import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
import app.models  # noqa: F401 — register all models
from app.services.job_store import bulk_upsert_jobs, record_api_usage, upsert_company, upsert_job


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

        bulk_upsert_jobs(db, [_job(company_name="Health Corp"), _job("js_2", company_name="Data Co")])
        count = db.query(Company).count()
        assert count == 2


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
