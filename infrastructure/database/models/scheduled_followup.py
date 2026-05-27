"""SQLAlchemy ORM model for scheduled_followups table."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class ScheduledFollowupModel(Base):
    __tablename__ = "scheduled_followups"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    followup_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    trigger_event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(sa.String(20), server_default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(sa.Integer, server_default="0", nullable=False)
    last_error: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    message_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_fu_pending", "scheduled_at", postgresql_where=sa.text("status = 'pending'")),
        sa.Index("ix_fu_user_status", "telegram_user_id", "status"),
    )
