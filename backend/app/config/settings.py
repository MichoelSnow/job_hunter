from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/jobs.db"

    # API Keys
    jsearchapi_key: str = ""   # OpenWebNinja JSearch — https://www.openwebninja.com/api/jsearch/docs
    serplyapi_key: str = ""    # Serply.io job search

    # Application
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    # Job Discovery
    max_jobs_per_query: int = 500
    api_request_delay_seconds: int = 1

    # Default search queries (can be extended via UI/criteria table)
    search_queries: list[str] = [
        "data director healthcare",
        "data leader healthcare",
        "head of data healthcare",
        "VP data healthcare",
        "chief data officer healthcare",
        "data director healthtech",
        "head of data healthtech",
    ]

    search_locations: list[str] = [
        "New York, NY",
        "Manhattan, NY",
        "Brooklyn, NY",
    ]

    # Scoring weights — only defined here, injected into ScoringEngine at construction
    user_to_job_weight: float = 0.6
    job_to_user_weight: float = 0.4

    # User-to-job sub-weights (must sum to 1.0)
    skill_match_weight: float = 0.50
    experience_match_weight: float = 0.25
    title_match_weight: float = 0.15
    education_match_weight: float = 0.10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
