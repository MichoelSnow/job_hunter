"""Shared fixtures for integration tests.

Uses FastAPI's TestClient with an in-memory SQLite database, overriding the
get_db dependency so no real database file is touched.
"""

from datetime import date

import app.models  # noqa: F401 — register all ORM models with Base
import pytest
from app.db.base import Base
from app.db.session import get_db
from app.models.job import Job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _make_engine_and_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # ensures all connections share the same in-memory DB
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Yield a bare SQLAlchemy session backed by an in-memory DB."""
    engine, SessionFactory = _make_engine_and_session()
    session = SessionFactory()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient with get_db overridden to use the in-memory session."""
    from main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_with_job(client, db_session):
    """TestClient + the integer ID of a pre-seeded job."""
    job = Job(
        title="Director of Data",
        description="Lead our data team in Manhattan.",
        location="Manhattan, NY",
        work_arrangement="in_office",
        application_url="https://example.com/apply",
        source="jsearch_api",
        discovered_date=date(2026, 4, 1),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return client, job.id
