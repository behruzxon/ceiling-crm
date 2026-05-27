"""SQLAlchemy ORM model for crm_report_delivery_audit."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class CRMReportDeliveryAuditModel(Base):
    __tablename__ = "crm_report_delivery_audit"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    report_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    delivery_channel: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    recipient_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    message_preview: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    __table_args__ = (
        sa.Index("ix_delivery_audit_report", "report_id", "created_at"),
        sa.Index("ix_delivery_audit_status", "status", "created_at"),
    )
