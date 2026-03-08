"""Add billing fields to tenants table.

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-03-08 10:00:00.000000

Adds trial and subscription tracking: billing_status, trial_ends_at,
subscription_expires_at.  Existing tenants are backfilled with
billing_status='trial' and trial_ends_at = created_at + 7 days.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1q2r3s4t5u6"
down_revision = "o0p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns as nullable
    op.add_column(
        "tenants",
        sa.Column("billing_status", sa.String(16), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # 2. Backfill existing tenants: trial status with retroactive trial window
    op.execute(
        sa.text(
            "UPDATE tenants SET billing_status = 'trial', "
            "trial_ends_at = created_at + interval '7 days' "
            "WHERE billing_status IS NULL"
        )
    )

    # 3. Make billing_status NOT NULL with server default for future inserts
    op.alter_column(
        "tenants",
        "billing_status",
        nullable=False,
        server_default="trial",
    )

    # 4. Add index for billing queries
    op.create_index(
        "ix_tenants_billing_status", "tenants", ["billing_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_billing_status", table_name="tenants")
    op.drop_column("tenants", "subscription_expires_at")
    op.drop_column("tenants", "trial_ends_at")
    op.drop_column("tenants", "billing_status")
