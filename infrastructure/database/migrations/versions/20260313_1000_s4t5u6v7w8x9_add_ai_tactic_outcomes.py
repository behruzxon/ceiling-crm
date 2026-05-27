"""Add ai_tactic_outcomes table for outcome-based learning.

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-03-13 10:00:00.000000+00:00
"""

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "ai_tactic_outcomes",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.BigInteger,
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("tactic_name", sa.String(64), nullable=False),
        sa.Column("objection_type", sa.String(32), nullable=True),
        sa.Column("lead_score_at_time", sa.Integer, server_default="0", nullable=False),
        sa.Column("stage_at_time", sa.String(32), nullable=True),
        sa.Column("lead_temperature_at_time", sa.String(16), nullable=True),
        sa.Column("outcome", sa.String(32), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_ato_outcome_created", "ai_tactic_outcomes", ["outcome", "created_at"])
    op.create_index("ix_ato_event_type", "ai_tactic_outcomes", ["event_type"])
    op.create_index("ix_ato_lead_created", "ai_tactic_outcomes", ["lead_id", "created_at"])
    op.create_index("ix_ato_user_created", "ai_tactic_outcomes", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ai_tactic_outcomes")
