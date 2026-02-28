"""add group_join_events table for group join tracking

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-02-28 12:00:00.000000

Changes
-------
New table: group_join_events
  Records the first time each user joins a tracked Telegram group.
  Re-joins after a leave are ignored (ON CONFLICT DO NOTHING).

  Columns:
    id         BIGINT IDENTITY PRIMARY KEY
    group_id   BIGINT NOT NULL              — Telegram chat_id of the group
    user_id    BIGINT NOT NULL              — Telegram user_id who joined
    joined_at  TIMESTAMPTZ DEFAULT NOW()    NOT NULL

  Constraints:
    UNIQUE (group_id, user_id)             — uq_group_join_events_group_user

  Indexes:
    ix_group_join_events_group_joined (group_id, joined_at) — period count queries
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i4j5k6l7m8n9"
down_revision = "h3i4j5k6l7m8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_join_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "group_id", "user_id",
            name="uq_group_join_events_group_user",
        ),
    )
    op.create_index(
        "ix_group_join_events_group_joined",
        "group_join_events",
        ["group_id", "joined_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_group_join_events_group_joined", table_name="group_join_events")
    op.drop_table("group_join_events")
