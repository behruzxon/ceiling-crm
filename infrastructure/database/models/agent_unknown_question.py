"""SQLAlchemy ORM model for agent_unknown_questions.

One row = one customer message where the bot likely failed / was uncertain /
hit a fallback or safety block and needs admin review. Privacy-safe: only a
sanitized preview + a hash are stored (see core.services.unknown_question_service).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AgentUnknownQuestionModel(Base):
    __tablename__ = "agent_unknown_questions"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default="telegram",
    )
    channel_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    crm_contact_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    telegram_chat_id_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    original_text_preview: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default="",
    )
    original_text_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        server_default="",
    )
    bot_reply_preview: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    reason: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default="ai_fallback",
    )
    intent: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    live_route: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    sdm_intent: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    sdm_next_action: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    order_readiness_score: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    severity: Mapped[str] = mapped_column(
        sa.String(10),
        nullable=False,
        server_default="medium",
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default="new",
    )
    admin_note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    __table_args__ = (
        sa.Index("ix_uq_created", "created_at"),
        sa.Index("ix_uq_status", "status"),
        sa.Index("ix_uq_reason", "reason"),
        sa.Index("ix_uq_severity", "severity"),
        sa.Index("ix_uq_text_hash", "original_text_hash"),
        sa.Index("ix_uq_contact", "crm_contact_id"),
        sa.Index(
            "ix_uq_dedupe",
            "original_text_hash",
            "channel_user_id",
            "reason",
            "created_at",
        ),
    )
