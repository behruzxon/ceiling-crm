"""Add unique partial index on provider_trans_id.

Ensures no two subscription_payments can share the same provider
transaction ID, preventing duplicate webhook processing at the
database level.  NULL values are excluded (PostgreSQL partial index).

Also drops the old non-unique index on provider_trans_id.

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-03-09 20:00:00.000000+00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "z2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old non-unique index
    op.drop_index("ix_sub_payments_provider_trans_id", table_name="subscription_payments")

    # Create unique partial index (NULLs excluded)
    op.create_index(
        "uq_sub_payments_provider_trans_id",
        "subscription_payments",
        ["provider_trans_id"],
        unique=True,
        postgresql_where=sa.text("provider_trans_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_sub_payments_provider_trans_id",
        table_name="subscription_payments",
    )

    # Restore old non-unique index
    op.create_index(
        "ix_sub_payments_provider_trans_id",
        "subscription_payments",
        ["provider_trans_id"],
    )
