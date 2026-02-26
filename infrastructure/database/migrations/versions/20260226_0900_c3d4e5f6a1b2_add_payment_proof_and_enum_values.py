"""add proof_file_id column and manual/rejected enum values

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-02-26 09:00:00.000000

Changes:
- payments.proof_file_id VARCHAR(512) NULL  — Telegram file_id of receipt photo/doc
- payment_method enum: add 'manual'
- payment_status enum: add 'rejected'

Note: ALTER TYPE ... ADD VALUE is transactional on PostgreSQL 12+.
      If running on PostgreSQL < 12, apply manually outside a transaction.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend enums — IF NOT EXISTS keeps the migration idempotent
    op.execute(sa.text("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'manual'"))
    op.execute(sa.text("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'rejected'"))

    # Add proof column
    op.add_column(
        "payments",
        sa.Column("proof_file_id", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "proof_file_id")
    # PostgreSQL does not support removing enum values;
    # downgrade drops the column only — enum values stay but are unused.
