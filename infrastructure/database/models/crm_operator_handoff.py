"""SQLAlchemy ORM model for crm_operator_handoff_requests."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class CRMOperatorHandoffModel(Base):
    __tablename__ = "crm_operator_handoff_requests"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(), primary_key=True,
    )
    contact_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True,
    )
    telegram_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True,
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="open",
    )
    priority: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="normal",
    )
    source: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, server_default="bot",
    )
    reason: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    user_message_preview: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True,
    )
    phone_masked: Mapped[str | None] = mapped_column(
        sa.String(30), nullable=True,
    )
    district: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    area_m2: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    ceiling_type: Mapped[str | None] = mapped_column(
        sa.String(50), nullable=True,
    )
    assigned_to_admin_id: Mapped[str | None] = mapped_column(
        sa.String(50), nullable=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        sa.JSON, nullable=True,
    )

    __table_args__ = (
        sa.Index("ix_handoff_contact_status", "contact_id", "status"),
        sa.Index(
            "ix_handoff_status_priority_created",
            "status", "priority", "created_at",
        ),
        sa.Index("ix_handoff_tg_user_status", "telegram_user_id", "status"),
        sa.Index("ix_handoff_created", "created_at"),
        sa.Index(
            "ix_handoff_assigned_status", "assigned_to_admin_id", "status",
        ),
    )
