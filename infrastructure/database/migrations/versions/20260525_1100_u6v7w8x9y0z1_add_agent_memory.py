"""Add customer_agent_memory table for per-user agent state.

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-05-25 11:00:00.000000+00:00
"""

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "customer_agent_memory",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("lead_id", sa.BigInteger, nullable=True),
        sa.Column("full_name", sa.String(128), nullable=True),
        sa.Column("phone_masked", sa.String(30), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("interested_designs", sa.JSON, server_default="[]", nullable=False),
        sa.Column("area_m2", sa.Float, nullable=True),
        sa.Column("ceiling_type", sa.String(50), nullable=True),
        sa.Column("estimated_price", sa.BigInteger, nullable=True),
        sa.Column("lead_temperature", sa.String(10), server_default="cold", nullable=False),
        sa.Column("last_event_type", sa.String(50), nullable=True),
        sa.Column("last_event_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("followup_enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("followup_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_followup_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_followup_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.String(50), nullable=True),
        sa.Column("memory_data", sa.JSON, server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_mem_temp", "customer_agent_memory", ["lead_temperature"])
    op.create_index("ix_agent_mem_next_fu", "customer_agent_memory", ["next_followup_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_mem_next_fu", table_name="customer_agent_memory")
    op.drop_index("ix_agent_mem_temp", table_name="customer_agent_memory")
    op.drop_table("customer_agent_memory")
