"""Add lost_reason column to leads table.

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-03-12 10:00:00.000000+00:00
"""

revision = "r3s4t5u6v7w8"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("lost_reason", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leads", "lost_reason")
