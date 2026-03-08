"""SQLAlchemy ORM model for group_join_events table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class GroupJoinEventModel(Base):
    """One row per unique (group, user) join.

    The UNIQUE constraint on (group_id, user_id) means we record only the
    *first* join — re-joins after a leave are intentionally ignored so that
    the period counts remain meaningful and non-inflated.
    """

    __tablename__ = "group_join_events"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    group_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

    # ── Tenant ─────────────────────────────────────────────────────────────
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenants.id"), nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_join_events_group_user"),
        sa.Index("ix_group_join_events_group_joined", "group_id", "joined_at"),
        sa.Index("ix_group_join_events_tenant_id", "tenant_id"),
    )
