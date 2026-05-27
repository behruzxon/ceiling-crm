"""SQLAlchemy ORM model for crm_daily_reports."""
from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class CRMDailyReportModel(Base):
    __tablename__ = "crm_daily_reports"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    report_date: Mapped[date] = mapped_column(sa.Date, nullable=False, unique=True)
    period_start: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(30), server_default="generated")
    delivery_mode: Mapped[str] = mapped_column(sa.String(20), server_default="disabled")
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    summary_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    recommendations_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    sent_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    __table_args__ = (sa.Index("ix_daily_report_status", "status"),)
