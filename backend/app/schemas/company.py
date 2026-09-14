from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyBase(BaseModel):
    name: str
    industry: str | None = None
    company_size: str | None = None
    funding_stage: str | None = None
    headquarters_location: str | None = None
    website_url: str | None = None
    careers_page_url: str | None = None
    logo_url: str | None = None
    description: str | None = None
    ats_type: str | None = None
    ats_id: str | None = None
    workday_board: str | None = None
    workday_instance: str | None = None
    html_selectors: dict[str, str] | None = None
    is_priority: bool = False


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(CompanyBase):
    name: str | None = None


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_scraped_at: datetime | None = None
    scrape_last_status: str | None = None
    scrape_last_error: str | None = None
    job_count: int = 0
    scrape_error: bool = False
    created_at: datetime
    updated_at: datetime
