"""SQLAlchemy ORM model for broadcasts table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType


class BroadcastModel(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(256), nullable=False)

    # ── Segment ──────────────────────────────────────────────────────────────
    segment_type: Mapped[str] = mapped_column(
        sa.Enum(SegmentType, name="segment_type"),
        nullable=False,
        server_default=SegmentType.ALL_PRIVATE.value,
    )
    lead_stage: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)

    # ── Payload ───────────────────────────────────────────────────────────────
    payload_type: Mapped[str] = mapped_column(
        sa.Enum(PayloadType, name="payload_type"),
        nullable=False,
        server_default=PayloadType.TEXT.value,
    )
    text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)

    # ── Legacy / compat columns (kept for existing rows) ─────────────────────
    message_template: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    media_file_id: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    media_type: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    segment_filter: Mapped[dict] = mapped_column(sa.JSON, server_default="{}")
    scheduled_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )

    # ── Status & counters ─────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        sa.Enum(BroadcastStatus, name="broadcast_status"),
        nullable=False,
        server_default=BroadcastStatus.DRAFT.value,
    )
    total: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    sent_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    failed_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    finished_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    created_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.Index("ix_broadcasts_status", "status"),
        sa.Index("ix_broadcasts_scheduled", "scheduled_at"),
    )
