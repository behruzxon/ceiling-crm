"""Add admin_users table for web admin panel authentication.

Revision ID: c5d6e7f8g9h0
Revises: b4c5d6e7f8g9
Create Date: 2026-03-10 08:00:00.000000

Creates admin_users table: web admin panel accounts (email + bcrypt password).
Separate from the Telegram-based users table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "c5d6e7f8g9h0"
down_revision: str = "b4c5d6e7f8g9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_admin_users_tenant_email", "admin_users", ["tenant_id", "email"],
    )
    op.create_index("ix_admin_users_tenant_id", "admin_users", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_users_tenant_id", table_name="admin_users")
    op.drop_constraint("uq_admin_users_tenant_email", "admin_users", type_="unique")
    op.drop_table("admin_users")
