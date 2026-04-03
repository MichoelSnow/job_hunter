import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models.company import Company
from app.services.company_enrichment import enrich_companies_from_config


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCompanyEnrichment:
    def test_enriches_existing_company_metadata_from_config(self, db):
        db.add(Company(name="Oscar Health"))
        db.commit()

        updated = enrich_companies_from_config(db)
        company = db.query(Company).filter(Company.name == "Oscar Health").first()

        assert updated >= 1
        assert company is not None
        assert company.ats_type == "greenhouse"
        assert company.ats_id == "oscar"
        assert company.careers_page_url is not None
        assert company.website_url is not None
        assert company.is_priority is True

    def test_inserts_missing_config_companies(self, db):
        db.add(Company(name="Some Other Company"))
        db.commit()

        before_count = db.query(Company).count()
        updated = enrich_companies_from_config(db)
        after_count = db.query(Company).count()

        oscar = db.query(Company).filter(Company.name == "Oscar Health").first()
        assert updated > 0
        assert after_count > before_count
        assert oscar is not None

    def test_sync_is_idempotent(self, db):
        first_changes = enrich_companies_from_config(db)
        second_changes = enrich_companies_from_config(db)
        assert first_changes > 0
        assert second_changes == 0
