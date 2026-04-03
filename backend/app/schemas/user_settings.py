from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserSettingsBase(BaseModel):
    search_queries: list[str] = Field(default_factory=list)
    filter_location_query: str = ""
    filter_title_query: str = ""
    filter_exclude_remote: bool = True
    filter_target_salary: int | None = None
    filter_include_missing_salary: bool = True


class UserSettingsUpdate(UserSettingsBase):
    pass


class UserSettingsResponse(UserSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime
