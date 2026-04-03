from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    title: str
    description: str
    location: str | None = None
    work_arrangement: str | None = None
    days_in_office: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    salary_period: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    posted_date: date | None = None
    closed_date: date | None = None
    application_url: str
    source_url: str | None = None
    source: str


class JobCreate(JobBase):
    external_id: str | None = None
    company_id: int | None = None
    discovered_date: date
    raw_data: dict[str, Any] | None = None


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None = None
    company_id: int | None = None
    company_name: str | None = None
    company_industry: str | None = None
    discovered_date: date
    is_active: bool
    match_score_user_to_job: float | None = None
    match_score_job_to_user: float | None = None
    overall_match_score: float | None = None
    description_html: str | None = None
    score_calculated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    total: int
    items: list[JobResponse]
