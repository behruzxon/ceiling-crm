"""SQLAlchemy ORM model for agent_setting_audit_logs table."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AgentSettingAuditLogModel(Base):
    __tablename__ = "agent_setting_audit_logs"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    setting_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    old_value_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    new_value_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    confirmation_token_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    rollback_snapshot_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    validation_result_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_audit_key_created", "setting_key", "created_at"),
        sa.Index("ix_audit_action_created", "action", "created_at"),
    )
