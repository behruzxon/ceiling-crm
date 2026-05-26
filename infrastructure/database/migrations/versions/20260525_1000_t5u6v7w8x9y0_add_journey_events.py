"""Add customer_journey_events table for tracking user actions.

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-05-25 10:00:00.000000+00:00
"""

revision = "t5u6v7w8x9y0"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "customer_journey_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", sa.JSON, server_default="{}", nullable=False),
        sa.Column("source_handler", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_journey_user_created", "customer_journey_events", ["user_id", "created_at"])
    op.create_index("ix_journey_type_created", "customer_journey_events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_journey_type_created", table_name="customer_journey_events")
    op.drop_index("ix_journey_user_created", table_name="customer_journey_events")
    op.drop_table("customer_journey_events")
