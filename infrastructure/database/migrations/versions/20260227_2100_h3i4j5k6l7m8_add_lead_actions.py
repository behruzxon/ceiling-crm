"""add lead_actions table for operator performance tracking

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-02-27 21:00:00.000000

Changes
-------
New table: lead_actions
  Records one row per admin inline-button press.

  Columns:
    id            BIGINT IDENTITY PRIMARY KEY
    lead_id       BIGINT FK leads(id) ON DELETE CASCADE  NOT NULL
    actor_user_id BIGINT                                 NOT NULL
    action_type   VARCHAR(32)                            NOT NULL
                  Values: hot | warm | cold | phone | measurement | note | block
    payload       JSON                                   NULL
    created_at    TIMESTAMPTZ DEFAULT NOW()              NOT NULL

  Indexes:
    ix_lead_actions_actor_created  (actor_user_id, created_at)  — operator stats queries
    ix_lead_actions_lead_created   (lead_id, created_at)        — per-lead history
    ix_lead_actions_created        (created_at)                 — time-range scans
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "h3i4j5k6l7m8"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_actions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.BigInteger(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_lead_actions_actor_created",
        "lead_actions",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_lead_actions_lead_created",
        "lead_actions",
        ["lead_id", "created_at"],
    )
    op.create_index(
        "ix_lead_actions_created",
        "lead_actions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_actions_created", table_name="lead_actions")
    op.drop_index("ix_lead_actions_lead_created", table_name="lead_actions")
    op.drop_index("ix_lead_actions_actor_created", table_name="lead_actions")
    op.drop_table("lead_actions")
