from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCriteriaBase(BaseModel):
    criterion_type: str
    criterion_value: str
    is_hard_requirement: bool = False
    weight: float = 1.0


class UserCriteriaCreate(UserCriteriaBase):
    pass


class UserCriteriaUpdate(UserCriteriaBase):
    criterion_type: str | None = None
    criterion_value: str | None = None


class UserCriteriaResponse(UserCriteriaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
