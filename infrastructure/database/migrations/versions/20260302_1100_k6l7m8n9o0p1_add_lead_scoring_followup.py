"""add lead_temperature, closing_confidence, next_follow_up_at, follow_up_count to leads

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-03-02 11:00:00.000000

Changes
-------
leads table:
  + lead_temperature   VARCHAR(16)            NULLABLE
      AI-assessed lead heat: "hot" | "warm" | "cold".
  + closing_confidence DOUBLE PRECISION       NULLABLE
      AI-assessed closing probability (0.0 – 1.0).
  + next_follow_up_at  TIMESTAMP WITH TIME ZONE  NULLABLE
      Scheduler uses this to send the next admin reminder.
  + follow_up_count    INTEGER  DEFAULT 0     NOT NULL
      How many follow-up reminders have been sent for this lead.

Index ix_leads_next_follow_up_at speeds up the scheduler query.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k6l7m8n9o0p1"
down_revision = "j5k6l7m8n9o0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("lead_temperature", sa.String(16), nullable=True))
    op.add_column("leads", sa.Column("closing_confidence", sa.Float(), nullable=True))
    op.add_column(
        "leads",
        sa.Column("next_follow_up_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column(
            "follow_up_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_index("ix_leads_next_follow_up_at", "leads", ["next_follow_up_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_next_follow_up_at", table_name="leads")
    op.drop_column("leads", "follow_up_count")
    op.drop_column("leads", "next_follow_up_at")
    op.drop_column("leads", "closing_confidence")
    op.drop_column("leads", "lead_temperature")
