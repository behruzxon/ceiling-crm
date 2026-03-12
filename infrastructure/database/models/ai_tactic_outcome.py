"""SQLAlchemy ORM model for ai_tactic_outcomes table — outcome-based learning."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AiTacticOutcomeModel(Base):
    __tablename__ = "ai_tactic_outcomes"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    # What happened
    event_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    tactic_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    objection_type: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)

    # Context snapshot
    lead_score_at_time: Mapped[int] = mapped_column(
        sa.Integer, server_default="0", nullable=False,
    )
    stage_at_time: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    lead_temperature_at_time: Mapped[str | None] = mapped_column(
        sa.String(16), nullable=True,
    )

    # Outcome (resolved by scheduler job)
    outcome: Mapped[str] = mapped_column(
        sa.String(32), server_default="pending", nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )

    __table_args__ = (
        sa.Index("ix_ato_outcome_created", "outcome", "created_at"),
        sa.Index("ix_ato_event_type", "event_type"),
        sa.Index("ix_ato_lead_created", "lead_id", "created_at"),
        sa.Index("ix_ato_user_created", "user_id", "created_at"),
    )
