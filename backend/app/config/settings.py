from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/jobs.db"

    # API Keys
    jsearchapi_key: str = ""  # OpenWebNinja JSearch — https://www.openwebninja.com/api/jsearch/docs
    serplyapi_key: str = ""  # Serply.io job search

    # Application
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    # Job Discovery
    api_request_delay_seconds: int = 1
    api_request_timeout_seconds: int = Field(default=60, ge=1, le=60)

    # JSearch: num_pages per request (1–10 costs 2x quota; 11–20 costs 3x quota).
    # 10 = 100 results per HTTP call at 2x quota cost — best efficiency on free plan.
    jsearch_num_pages: int = 10

    # Serply: results per request (max 100).
    serply_num_results: int = 100

    # Scoring weights — only defined here, injected into ScoringEngine at construction
    user_to_job_weight: float = 0.6
    job_to_user_weight: float = 0.4

    # User-to-job sub-weights (must sum to 1.0)
    skill_match_weight: float = 0.50
    experience_match_weight: float = 0.25
    title_match_weight: float = 0.15
    education_match_weight: float = 0.10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        raise ValueError("debug must be a boolean-compatible value")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return []
            return [v.strip() for v in normalized.split(",") if v.strip()]
        raise ValueError("cors_origins must be a list or comma-separated string")


settings = Settings()
