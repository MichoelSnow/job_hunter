from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserCriteria(Base):
    __tablename__ = "user_criteria"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    criterion_type: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_hard_requirement: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
