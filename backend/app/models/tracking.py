from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobSearchQuery(Base):
    __tablename__ = "job_search_queries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    results_count: Mapped[int | None] = mapped_column(Integer)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)


class ApiUsageTracking(Base):
    __tablename__ = "api_usage_tracking"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    api_name: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(255))
    request_count: Mapped[int] = mapped_column(Integer, default=1)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_estimate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
