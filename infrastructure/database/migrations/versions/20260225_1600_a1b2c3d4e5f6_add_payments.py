"""add payments table

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-02-25 16:00:00.000000

Creates the `payments` table together with the `payment_status` and
`payment_method` PostgreSQL enum types.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id",          sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("lead_id",     sa.BigInteger(), nullable=False),
        sa.Column(
            "amount", sa.BigInteger(), nullable=False,
            comment="Amount in UZS (so'm), integer — no fractional currency",
        ),
        sa.Column("method",      sa.Enum("cash", "card", "transfer",  name="payment_method"),  nullable=False),
        sa.Column("status",      sa.Enum("pending", "paid", "canceled", "refunded", name="payment_status"), nullable=False, server_default="pending"),
        sa.Column("paid_at",     sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column("notes",       sa.Text(), nullable=True),
        sa.Column("created_by",  sa.BigInteger(), nullable=True),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",  sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"],    ["leads.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],  ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_lead",    "payments", ["lead_id"])
    op.create_index("ix_payments_status",  "payments", ["status"])
    op.create_index("ix_payments_paid_at", "payments", ["paid_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_paid_at", table_name="payments")
    op.drop_index("ix_payments_status",  table_name="payments")
    op.drop_index("ix_payments_lead",    table_name="payments")
    op.drop_table("payments")
    op.execute("DROP TYPE IF EXISTS payment_method")
    op.execute("DROP TYPE IF EXISTS payment_status")
