from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.company import Company


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    # 'remote', 'hybrid', 'in_office', 'unknown'
    work_arrangement: Mapped[str | None] = mapped_column(String(100))
    days_in_office: Mapped[int | None] = mapped_column(Integer)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    salary_period: Mapped[str | None] = mapped_column(String(50))  # 'annual', 'hourly'
    # 'full_time', 'part_time', 'contract'
    employment_type: Mapped[str | None] = mapped_column(String(100))
    # 'entry', 'mid', 'senior', 'lead', 'executive'
    experience_level: Mapped[str | None] = mapped_column(String(100))
    posted_date: Mapped[date | None] = mapped_column(Date)
    discovered_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    application_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    # 'jsearch_api', 'greenhouse', 'lever', 'html_scraper', 'manual'
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    match_score_user_to_job: Mapped[float | None] = mapped_column(Float)
    match_score_job_to_user: Mapped[float | None] = mapped_column(Float)
    overall_match_score: Mapped[float | None] = mapped_column(Float)
    score_calculated_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company | None] = relationship("Company", back_populates="jobs")
    requirements: Mapped[list[JobRequirement]] = relationship(
        "JobRequirement", back_populates="job", cascade="all, delete-orphan"
    )
    application: Mapped[Application | None] = relationship(
        "Application", back_populates="job", uselist=False
    )

    __table_args__ = (
        Index("idx_jobs_company", "company_id"),
        Index("idx_jobs_posted_date", "posted_date"),
        Index("idx_jobs_discovered_date", "discovered_date"),
        Index("idx_jobs_match_score", "overall_match_score"),
        Index("idx_jobs_is_active", "is_active"),
        Index("idx_jobs_location", "location"),
    )

    @property
    def company_name(self) -> str | None:
        return self.company.name if self.company else None

    @property
    def company_industry(self) -> str | None:
        return self.company.industry if self.company else None


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    # 'skill', 'experience', 'education', 'certification'
    requirement_type: Mapped[str | None] = mapped_column(String(100))
    requirement_value: Mapped[str | None] = mapped_column(String(500))
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    job: Mapped[Job] = relationship("Job", back_populates="requirements")
