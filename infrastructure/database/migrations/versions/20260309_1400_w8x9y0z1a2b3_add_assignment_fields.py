"""Add assigned_at and assignment_reason to leads.

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-03-09 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("assignment_reason", sa.String(200), nullable=True),
    )
    # Backfill: set assigned_at = updated_at for already-assigned leads
    op.execute(
        "UPDATE leads SET assigned_at = updated_at "
        "WHERE assigned_manager_id IS NOT NULL AND assigned_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("leads", "assignment_reason")
    op.drop_column("leads", "assigned_at")
