"""SQLAlchemy ORM model for admin_groups table.

Tracks Telegram groups where the bot has been added as an admin.
Used as the recipient list for ADMIN_GROUPS broadcasts.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AdminGroupModel(Base):
    __tablename__ = "admin_groups"

    chat_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
