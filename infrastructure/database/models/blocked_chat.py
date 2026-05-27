"""SQLAlchemy ORM model for blocked_chats table.

Tracks chat IDs (private users AND groups) that have permanently rejected
the bot.  Used to exclude them from all future broadcasts without hitting
Telegram every time.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class BlockedChatModel(Base):
    __tablename__ = "blocked_chats"

    chat_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)

    # Latest failure reason.  One of: 'blocked' | 'forbidden' | 'other'
    reason: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    # Timestamps — never touched by code after first insert except via upsert.
    first_seen_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # How many broadcast runs have hit this chat_id as unreachable.
    seen_count: Mapped[int] = mapped_column(sa.Integer, server_default="1", nullable=False)

    __table_args__ = (sa.Index("ix_blocked_chats_last_seen_at", "last_seen_at"),)
