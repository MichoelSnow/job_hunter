import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.db.session import create_tables

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
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

    from app.services.text_parser import load_user_profile

    app.state.user_profile = load_user_profile()
    logger.info("Loaded user profile for %s", app.state.user_profile.get("user", {}).get("name", "unknown"))


from app.api import analytics, applications, companies, criteria, jobs  # noqa: E402

app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(criteria.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
