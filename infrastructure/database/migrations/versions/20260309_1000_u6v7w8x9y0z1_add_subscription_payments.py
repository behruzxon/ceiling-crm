"""Add subscription_payments table and billing plan columns to tenants.

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-03-09 10:00:00.000000+00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create enum types ────────────────────────────────────────────
    sub_provider = sa.Enum(
        "click", "payme", "manual",
        name="sub_payment_provider",
    )
    sub_provider.create(op.get_bind(), checkfirst=True)

    sub_status = sa.Enum(
        "pending", "preparing", "paid", "canceled", "failed",
        name="sub_payment_status",
    )
    sub_status.create(op.get_bind(), checkfirst=True)

    # ── 2. Create subscription_payments table ───────────────────────────
    op.create_table(
        "subscription_payments",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "tenant_id", sa.BigInteger,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sub_provider, nullable=False),
        sa.Column("status", sub_status, nullable=False, server_default="pending"),
        sa.Column("amount", sa.BigInteger, nullable=False, comment="Amount in UZS"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="UZS"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "merchant_trans_id", sa.String(128), nullable=False, unique=True,
            comment="Our unique transaction ID sent to provider",
        ),
        sa.Column(
            "provider_trans_id", sa.String(128), nullable=True,
            comment="Transaction ID from Click/Payme",
        ),
        sa.Column("extension_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("provider_meta", JSONB, nullable=False, server_default="{}"),
    )

    op.create_index("ix_sub_payments_tenant_id", "subscription_payments", ["tenant_id"])
    op.create_index("ix_sub_payments_status", "subscription_payments", ["status"])
    op.create_index(
        "ix_sub_payments_provider_trans_id",
        "subscription_payments",
        ["provider_trans_id"],
    )

    # ── 3. Add billing columns to tenants ───────────────────────────────
    op.add_column(
        "tenants",
        sa.Column("billing_plan", sa.String(32), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "monthly_price_uzs", sa.BigInteger, nullable=True,
            comment="Monthly subscription price in UZS (so'm), integer",
        ),
    )

    # Backfill
    op.execute(
        sa.text(
            "UPDATE tenants SET billing_plan = 'basic', monthly_price_uzs = 0 "
            "WHERE billing_plan IS NULL"
        )
    )

    # Make NOT NULL with defaults
    op.alter_column("tenants", "billing_plan", nullable=False, server_default="basic")
    op.alter_column("tenants", "monthly_price_uzs", nullable=False, server_default="0")


def downgrade() -> None:
    op.drop_column("tenants", "monthly_price_uzs")
    op.drop_column("tenants", "billing_plan")

    op.drop_index("ix_sub_payments_provider_trans_id", table_name="subscription_payments")
    op.drop_index("ix_sub_payments_status", table_name="subscription_payments")
    op.drop_index("ix_sub_payments_tenant_id", table_name="subscription_payments")
    op.drop_table("subscription_payments")

    sa.Enum(name="sub_payment_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sub_payment_provider").drop(op.get_bind(), checkfirst=True)
