"""Add blocked_chats table for broadcast auto-clean.

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-03-03 16:00:00.000000

Changes
-------
1. blocked_chats table — persists permanently unreachable chat IDs
   (private users who blocked the bot, groups the bot was kicked from,
   deleted accounts, etc.).

   Columns:
     chat_id       BIGINT  PK — works for both private (>0) and group (<0) IDs
     reason        TEXT    — 'blocked' | 'forbidden' | 'other'
     first_seen_at TIMESTAMPTZ  — when this chat was first flagged
     last_seen_at  TIMESTAMPTZ  — most recent failure timestamp
     seen_count    INT          — total times this chat was attempted

2. Index on last_seen_at — supports future cleanup jobs that purge old
   entries (e.g. users who may have un-blocked the bot after months).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m8n9o0p1q2r3"
down_revision = "l7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blocked_chats",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "seen_count",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chat_id"),
    )
    op.create_index(
        "ix_blocked_chats_last_seen_at",
        "blocked_chats",
        ["last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_blocked_chats_last_seen_at", table_name="blocked_chats")
    op.drop_table("blocked_chats")
