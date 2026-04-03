import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parents[3]


def _resolve_database_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url

    raw_path = url.removeprefix("sqlite:///")
    if raw_path == ":memory:":
        return url

    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = (_REPO_ROOT / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


_database_url = _resolve_database_url(settings.database_url)

engine = create_engine(
    _database_url,
    connect_args={"check_same_thread": False} if "sqlite" in _database_url else {},
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if "sqlite" in _database_url:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables from ORM models. Used during development (pre-Alembic)."""
    from app.db.base import Base
    import app.models  # noqa: F401 — registers all models with Base

    logger.info("Creating database tables")
    Base.metadata.create_all(bind=engine)
    if "sqlite" in _database_url:
        _ensure_sqlite_job_columns()
        _ensure_sqlite_company_columns()
        _ensure_sqlite_user_settings_columns()


def _ensure_sqlite_job_columns() -> None:
    """Best-effort additive schema updates for local SQLite while Alembic is out of scope."""
    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(jobs)").fetchall()
        }
        if "closed_date" not in columns:
            logger.info("Adding missing jobs.closed_date column")
            conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN closed_date DATE")
        if "passes_user_filters" not in columns:
            logger.info("Adding missing jobs.passes_user_filters column")
            conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN passes_user_filters BOOLEAN DEFAULT 1")
        conn.exec_driver_sql(
            "UPDATE jobs SET passes_user_filters = 1 WHERE passes_user_filters IS NULL"
        )


def _ensure_sqlite_company_columns() -> None:
    """Best-effort additive company schema updates for local SQLite."""
    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(companies)").fetchall()
        }
        if "workday_board" not in columns:
            logger.info("Adding missing companies.workday_board column")
            conn.exec_driver_sql("ALTER TABLE companies ADD COLUMN workday_board VARCHAR(255)")
        if "workday_instance" not in columns:
            logger.info("Adding missing companies.workday_instance column")
            conn.exec_driver_sql("ALTER TABLE companies ADD COLUMN workday_instance VARCHAR(50)")
        if "html_selectors" not in columns:
            logger.info("Adding missing companies.html_selectors column")
            conn.exec_driver_sql("ALTER TABLE companies ADD COLUMN html_selectors JSON")


def _ensure_sqlite_user_settings_columns() -> None:
    import json

    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "user_settings" not in tables:
            return
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(user_settings)").fetchall()
        }
        if "filter_locations" not in columns:
            logger.info("Adding missing user_settings.filter_locations column")
            conn.exec_driver_sql("ALTER TABLE user_settings ADD COLUMN filter_locations JSON")
        if "filter_title_keywords" not in columns:
            logger.info("Adding missing user_settings.filter_title_keywords column")
            conn.exec_driver_sql("ALTER TABLE user_settings ADD COLUMN filter_title_keywords JSON")
        if "filter_target_salary" not in columns:
            logger.info("Adding missing user_settings.filter_target_salary column")
            conn.exec_driver_sql("ALTER TABLE user_settings ADD COLUMN filter_target_salary INTEGER")
        if "filter_include_missing_salary" not in columns:
            logger.info("Adding missing user_settings.filter_include_missing_salary column")
            conn.exec_driver_sql(
                "ALTER TABLE user_settings ADD COLUMN filter_include_missing_salary BOOLEAN DEFAULT 1"
            )
        conn.exec_driver_sql(
            "UPDATE user_settings SET filter_locations = search_locations "
            "WHERE filter_locations IS NULL"
        )
        default_keywords_json = json.dumps(
            ["director", "vp", "vice president", "head of", "chief", "lead", "manager", "principal"]
        )
        if "filter_require_leadership" in columns:
            conn.exec_driver_sql(
                "UPDATE user_settings SET filter_title_keywords = ? "
                "WHERE filter_title_keywords IS NULL AND filter_require_leadership = 1",
                (default_keywords_json,),
            )
            conn.exec_driver_sql(
                "UPDATE user_settings SET filter_title_keywords = '[]' "
                "WHERE filter_title_keywords IS NULL AND filter_require_leadership = 0"
            )
        conn.exec_driver_sql(
            "UPDATE user_settings SET filter_title_keywords = ? "
            "WHERE filter_title_keywords IS NULL",
            (default_keywords_json,),
        )
        conn.exec_driver_sql(
            "UPDATE user_settings SET filter_include_missing_salary = 1 "
            "WHERE filter_include_missing_salary IS NULL"
        )
