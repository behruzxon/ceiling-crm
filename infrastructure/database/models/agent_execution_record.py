"""SQLAlchemy ORM model for agent_execution_records table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AgentExecutionRecordModel(Base):
    __tablename__ = "agent_execution_records"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    execution_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, unique=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    mode: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    channel: Mapped[str | None] = mapped_column(sa.String(30), nullable=True)
    payload_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    result_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    trace_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    message_text_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

    __table_args__ = (
        sa.Index("ix_exec_user_created", "telegram_user_id", "created_at"),
        sa.Index("ix_exec_status_expires", "status", "expires_at"),
        sa.Index("ix_exec_mode_status", "mode", "status"),
    )
