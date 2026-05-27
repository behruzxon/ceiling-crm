"""SQLAlchemy ORM models for crm_campaign_drafts and crm_campaign_audit_logs."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class CRMCampaignDraftModel(Base):
    __tablename__ = "crm_campaign_drafts"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    segment_key: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), server_default="draft")
    message_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    recipient_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    excluded_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    safety_status: Mapped[str] = mapped_column(sa.String(20), server_default="pending")
    safety_reasons_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    filters_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    preview_recipients_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    __table_args__ = (
        sa.Index("ix_campaign_segment", "segment_key"),
        sa.Index("ix_campaign_status", "status"),
        sa.Index("ix_campaign_created", "created_at"),
        sa.Index("ix_campaign_created_by", "created_by"),
    )


class CRMCampaignAuditLogModel(Base):
    __tablename__ = "crm_campaign_audit_logs"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    actor_admin_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), server_default="success")
    reason: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    __table_args__ = (
        sa.Index("ix_camp_audit_campaign", "campaign_id", "created_at"),
        sa.Index("ix_camp_audit_actor", "actor_admin_id", "created_at"),
        sa.Index("ix_camp_audit_action", "action", "created_at"),
        sa.Index("ix_camp_audit_status", "status", "created_at"),
    )
