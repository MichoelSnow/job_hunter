from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_queries: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    search_locations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    filter_location_query: Mapped[str] = mapped_column(nullable=False, default="")
    filter_title_query: Mapped[str] = mapped_column(nullable=False, default="")
    filter_exclude_remote: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    filter_target_salary: Mapped[int | None] = mapped_column(Integer)
    filter_include_missing_salary: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    matching_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matching_experience_years: Mapped[int | None] = mapped_column(Integer)
    matching_current_title: Mapped[str | None] = mapped_column(String(255))
    matching_resume_path: Mapped[str | None] = mapped_column(String(500))
    matching_resume_mtime: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
