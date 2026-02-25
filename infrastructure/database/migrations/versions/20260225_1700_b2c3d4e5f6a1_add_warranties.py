"""add warranties table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-02-25 17:00:00.000000

Creates the `warranties` table — one row per lead (UNIQUE constraint).
No new enum types required.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warranties",
        sa.Column("id",               sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("lead_id",          sa.BigInteger(), nullable=False),
        sa.Column("issued_at",        sa.Date(),       nullable=False),
        sa.Column("expires_at",       sa.Date(),       nullable=False),
        sa.Column("warranty_card_no", sa.String(64),   nullable=True),
        sa.Column("notes",            sa.Text(),       nullable=True),
        sa.Column("created_by",       sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"],   ["leads.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", name="uq_warranties_lead_id"),
    )
    op.create_index("ix_warranties_lead",       "warranties", ["lead_id"])
    op.create_index("ix_warranties_expires_at", "warranties", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_warranties_expires_at", table_name="warranties")
    op.drop_index("ix_warranties_lead",       table_name="warranties")
    op.drop_table("warranties")
