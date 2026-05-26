"""SQLAlchemy ORM model for customer_agent_memory table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AgentMemoryModel(Base):
    __tablename__ = "customer_agent_memory"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, unique=True)
    lead_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    full_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    phone_masked: Mapped[str | None] = mapped_column(sa.String(30), nullable=True)
    district: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    interested_designs: Mapped[dict] = mapped_column(sa.JSON, server_default="[]", nullable=False)
    area_m2: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    ceiling_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    estimated_price: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    lead_temperature: Mapped[str] = mapped_column(sa.String(10), server_default="cold", nullable=False)
    last_event_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    followup_enabled: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"), nullable=False)
    followup_count: Mapped[int] = mapped_column(sa.Integer, server_default="0", nullable=False)
    last_followup_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    next_followup_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    admin_escalation_count: Mapped[int] = mapped_column(sa.Integer, server_default="0", nullable=False)
    last_admin_escalation_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    admin_escalation_reason: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    memory_data: Mapped[dict] = mapped_column(sa.JSON, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_agent_mem_temp", "lead_temperature"),
        sa.Index("ix_agent_mem_next_fu", "next_followup_at"),
    )
