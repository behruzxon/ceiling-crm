"""SQLAlchemy ORM model for agent_runtime_settings table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AgentRuntimeSettingModel(Base):
    __tablename__ = "agent_runtime_settings"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    key: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)
    value_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    value_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(30), server_default="control_center")
    risk_level: Mapped[str] = mapped_column(sa.String(20), server_default="low")
    description: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"))

    __table_args__ = (
        sa.Index("ix_runtime_setting_active", "is_active"),
    )
