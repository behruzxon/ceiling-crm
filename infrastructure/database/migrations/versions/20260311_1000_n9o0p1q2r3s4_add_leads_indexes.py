"""Add missing indexes on leads table for query performance.

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-03-11 10:00:00.000000

Changes
-------
1. leads(created_at) — used by get_leads_for_analytics, search with created_after/before
2. leads(source_group_id) — FK column, used in group-based lead lookups
3. leads(user_id, created_at DESC) — composite for list_by_user, get_by_user_id ordering
"""

from __future__ import annotations

from alembic import op

revision = "n9o0p1q2r3s4"
down_revision = "m8n9o0p1q2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_leads_created_at", "leads", ["created_at"])
    op.create_index("ix_leads_source_group_id", "leads", ["source_group_id"])
    op.create_index(
        "ix_leads_user_id_created_at",
        "leads",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_leads_user_id_created_at", table_name="leads")
    op.drop_index("ix_leads_source_group_id", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
