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
    api_request_delay_seconds: int = 1

    # JSearch: num_pages per request (1–10 costs 2x quota; 11–20 costs 3x quota).
    # 10 = 100 results per HTTP call at 2x quota cost — best efficiency on free plan.
    jsearch_num_pages: int = 10

    # Serply: results per request (max 100).
    serply_num_results: int = 100

    # Default search queries — kept broad so each query covers a wide role/industry range.
    # Fewer queries = fewer API requests. 3 queries × 1 location = 3 HTTP calls per client.
    search_queries: list[str] = [
        "director OR head OR VP data healthcare OR healthtech New York",
        "chief data officer healthcare OR healthtech New York",
        "data leader analytics healthcare OR healthtech New York",
    ]

    # Single metro location — NYC search results naturally include Manhattan and Brooklyn.
    search_locations: list[str] = [
        "New York, NY",
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
