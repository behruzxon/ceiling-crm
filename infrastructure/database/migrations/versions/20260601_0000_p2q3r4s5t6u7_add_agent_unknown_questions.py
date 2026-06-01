"""add agent_unknown_questions

Captures customer messages where the bot likely failed, was uncertain, hit a
fallback / OpenAI error, was safety-blocked, or otherwise needs admin review.
Read-only feedback-loop foundation — no bot behaviour change, no sends.

Privacy: only a sanitized preview (phones masked, tokens/URLs/keys redacted) is
stored, plus a SHA-256 hash of the normalized text for dedupe. Raw messages,
phone numbers, and secrets are never persisted.

Revision ID: p2q3r4s5t6u7
Revises: 4869f6eb9fbb
Create Date: 2026-06-01 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p2q3r4s5t6u7"
down_revision = "4869f6eb9fbb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_unknown_questions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="telegram"),
        sa.Column("channel_user_id", sa.BigInteger, nullable=True),
        sa.Column("crm_contact_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_chat_id_hash", sa.String(64), nullable=True),
        sa.Column("original_text_preview", sa.Text, nullable=False, server_default=""),
        sa.Column("original_text_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("bot_reply_preview", sa.Text, nullable=True),
        sa.Column("reason", sa.String(40), nullable=False, server_default="ai_fallback"),
        sa.Column("intent", sa.String(40), nullable=True),
        sa.Column("live_route", sa.String(40), nullable=True),
        sa.Column("sdm_intent", sa.String(40), nullable=True),
        sa.Column("sdm_next_action", sa.String(40), nullable=True),
        sa.Column("order_readiness_score", sa.Integer, nullable=True),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("admin_note", sa.Text, nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(50), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_uq_created", "agent_unknown_questions", ["created_at"])
    op.create_index("ix_uq_status", "agent_unknown_questions", ["status"])
    op.create_index("ix_uq_reason", "agent_unknown_questions", ["reason"])
    op.create_index("ix_uq_severity", "agent_unknown_questions", ["severity"])
    op.create_index("ix_uq_text_hash", "agent_unknown_questions", ["original_text_hash"])
    op.create_index("ix_uq_contact", "agent_unknown_questions", ["crm_contact_id"])
    op.create_index(
        "ix_uq_dedupe",
        "agent_unknown_questions",
        ["original_text_hash", "channel_user_id", "reason", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("agent_unknown_questions")
