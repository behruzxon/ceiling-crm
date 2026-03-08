"""Add business_type column to tenants table.

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-03-07 13:00:00.000000

Stores the business vertical (ceiling/restaurant/auto_service/clinic/other)
so that edit flows can resolve templates without a fallback guess.
Existing rows default to 'other'.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o0p1q2r3s4t5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add column as nullable first so existing rows aren't blocked
    op.add_column(
        "tenants",
        sa.Column("business_type", sa.String(32), nullable=True),
    )

    # 2. Backfill: VashPotolok → "ceiling", everything else → "other"
    op.execute(
        sa.text(
            "UPDATE tenants SET business_type = 'ceiling' "
            "WHERE slug = 'vashpotolok' AND business_type IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE tenants SET business_type = 'other' "
            "WHERE business_type IS NULL"
        )
    )

    # 3. Now make it NOT NULL with a server default for future inserts
    op.alter_column(
        "tenants",
        "business_type",
        nullable=False,
        server_default="other",
    )


def downgrade() -> None:
    op.drop_column("tenants", "business_type")
