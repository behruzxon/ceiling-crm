"""Add scoring engine signal columns to leads.

Revision ID: s4t5u6v7w8x9
Revises: q2r3s4t5u6v7
Create Date: 2026-03-08 14:00:00.000000+00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s4t5u6v7w8x9"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("urgency_signal", sa.String(8), nullable=True))
    op.add_column("leads", sa.Column("budget_signal", sa.String(8), nullable=True))
    op.add_column("leads", sa.Column("engagement_signal", sa.String(8), nullable=True))
    op.add_column("leads", sa.Column("objection_signal", sa.String(8), nullable=True))
    op.add_column("leads", sa.Column("scoring_reasons", sa.JSON, nullable=True))
    op.add_column(
        "leads",
        sa.Column("last_scored_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column(
            "operator_attention",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
    )

    op.create_index(
        "ix_leads_operator_attention",
        "leads",
        ["operator_attention"],
        postgresql_where=sa.text("operator_attention = true"),
    )
    op.create_index("ix_leads_last_scored_at", "leads", ["last_scored_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_last_scored_at", table_name="leads")
    op.drop_index("ix_leads_operator_attention", table_name="leads")
    op.drop_column("leads", "operator_attention")
    op.drop_column("leads", "last_scored_at")
    op.drop_column("leads", "scoring_reasons")
    op.drop_column("leads", "objection_signal")
    op.drop_column("leads", "engagement_signal")
    op.drop_column("leads", "budget_signal")
    op.drop_column("leads", "urgency_signal")
