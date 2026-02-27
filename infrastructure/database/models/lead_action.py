"""SQLAlchemy ORM model for lead_actions table.

Each row records one admin button press on a lead card:
  lead_id       — which lead was acted upon
  actor_user_id — Telegram user ID of the operator
  action_type   — hot | warm | cold | phone | measurement | note | block
  payload       — optional JSON context (e.g. {"note": "text"})
  created_at    — UTC timestamp (auto-set by DB)
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class LeadActionModel(Base):
    __tablename__ = "lead_actions"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    action_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    payload: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Primary query pattern: "all actions by operator in time window"
        sa.Index("ix_lead_actions_actor_created", "actor_user_id", "created_at"),
        # Secondary: "all actions on a specific lead"
        sa.Index("ix_lead_actions_lead_created", "lead_id", "created_at"),
        # Broad time-range scans / retention cleanup
        sa.Index("ix_lead_actions_created", "created_at"),
    )
