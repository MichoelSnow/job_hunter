import logging
import logging.handlers
from pathlib import Path

from app.api import analytics, applications, companies, jobs, user
from app.api import settings as app_settings_api
from app.config.settings import settings
from app.db.session import create_tables
from app.services.text_parser import load_user_profile
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_log_level = logging.DEBUG if settings.debug else logging.INFO
_log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter(_log_format))

# Rotating file handler — 5 MB per file, keep 3 backups
_log_dir = Path(__file__).parents[1] / "logs"
_log_dir.mkdir(exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    _log_dir / "app.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(_log_format))

logging.basicConfig(level=_log_level, handlers=[_console, _file_handler])
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Job Search API",
    description="Personal job search aggregation and tracking tool",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting up — creating tables if needed")
    create_tables()

    app.state.user_profile = load_user_profile()
    logger.info(
        "Loaded user profile for %s", app.state.user_profile.get("user", {}).get("name", "unknown")
    )


app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(app_settings_api.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(user.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
