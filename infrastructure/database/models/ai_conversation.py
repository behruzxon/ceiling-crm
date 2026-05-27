"""SQLAlchemy ORM model for ai_conversations table.

Stores a rolling window of the last 12 messages (role + text) and an
auto-generated short summary for each user so the AI handler can maintain
conversation continuity across sessions.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AiConversationModel(Base):
    __tablename__ = "ai_conversations"

    user_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    # Rolling window of {"role": "user"|"assistant", "text": "..."} dicts
    last_messages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # Short 2-4 line summary, regenerated every N turns
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Latest AI-assessed lead temperature ("hot" | "warm" | "cold")
    lead_temperature: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    # Latest AI-assessed closing confidence (0.0 – 1.0)
    closing_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
