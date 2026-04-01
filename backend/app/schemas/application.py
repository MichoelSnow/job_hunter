from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

APPLICATION_STATUSES = [
    "interested",
    "applied",
    "phone_screen",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]


class ApplicationBase(BaseModel):
    status: str
    applied_date: date | None = None
    last_contact_date: date | None = None
    next_action_date: date | None = None
    referral_source: str | None = None
    notes: str | None = None
    cover_letter: str | None = None
    resume_version: str | None = None
    metadata_: dict[str, Any] | None = None


class ApplicationCreate(ApplicationBase):
    job_id: int


class ApplicationUpdate(ApplicationBase):
    status: str | None = None


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    created_at: datetime
    updated_at: datetime


class StatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    old_status: str | None
    new_status: str
    changed_at: datetime
    notes: str | None
