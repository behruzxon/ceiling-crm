"""Add admin escalation columns to customer_agent_memory.

Revision ID: w8x9y0z1a2b3a
Revises: v7w8x9y0z1a2
Create Date: 2026-05-25 13:00:00.000000+00:00

NOTE: revision id was originally "w8x9y0z1a2b3" but collided with
``20260526_0500_w8x9y0z1a2b3_add_agent_execution_records.py``. The
duplicate prevented a clean ``alembic upgrade heads`` on a fresh
DB. Renamed here to ``w8x9y0z1a2b3a`` so both branches coexist and
get merged by a follow-up merge revision.
"""

revision = "w8x9y0z1a2b3a"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "customer_agent_memory",
        sa.Column("admin_escalation_count", sa.Integer, server_default="0", nullable=False),
    )
    op.add_column(
        "customer_agent_memory",
        sa.Column("last_admin_escalation_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_agent_memory",
        sa.Column("admin_escalation_reason", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_agent_memory", "admin_escalation_reason")
    op.drop_column("customer_agent_memory", "last_admin_escalation_at")
    op.drop_column("customer_agent_memory", "admin_escalation_count")
