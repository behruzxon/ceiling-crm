"""SQLAlchemy ORM model for group_settings table.

One row per Telegram group/supergroup.  Rows are created on first /admin
call with all columns defaulting to the values defined here.
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class GroupSettingsModel(Base):
    __tablename__ = "group_settings"

    chat_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)

    # ── Moderation toggles ────────────────────────────────────────────────
    welcome_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="true"
    )
    welcome_autodelete_seconds: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="3600"
    )
    captcha_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="false"
    )
    link_block_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="true"
    )
    flood_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="false"
    )
    logs_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="true"
    )

    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
