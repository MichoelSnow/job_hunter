from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_queries: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    search_locations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    filter_locations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    filter_title_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    filter_exclude_remote: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    filter_target_salary: Mapped[int | None] = mapped_column(Integer)
    filter_include_missing_salary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
