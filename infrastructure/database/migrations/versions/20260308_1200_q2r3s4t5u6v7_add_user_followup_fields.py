"""Add user-facing follow-up tracking fields to leads.

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-03-08 12:00:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1: Add columns (all have safe defaults)
    op.add_column(
        "leads",
        sa.Column(
            "user_followup_stage",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "user_followup_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "user_followup_closed",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )

    # Phase 2: Partial index for scheduler queries
    op.create_index(
        "ix_leads_user_followup_at",
        "leads",
        ["user_followup_at"],
        postgresql_where=sa.text(
            "user_followup_at IS NOT NULL AND NOT user_followup_closed"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_leads_user_followup_at", table_name="leads")
    op.drop_column("leads", "user_followup_closed")
    op.drop_column("leads", "user_followup_at")
    op.drop_column("leads", "user_followup_stage")
