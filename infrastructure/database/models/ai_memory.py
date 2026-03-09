"""SQLAlchemy ORM model for ai_user_memory table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AiMemoryModel(Base):
    __tablename__ = "ai_user_memory"

    # ── Composite PK: (tenant_id, user_id) ─────────────────────────────────
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenants.id"), nullable=False,
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("tenant_id", "user_id"),
        sa.Index("ix_ai_user_memory_tenant_id", "tenant_id"),
        sa.Index("ix_ai_user_memory_user_id", "user_id"),
    )
