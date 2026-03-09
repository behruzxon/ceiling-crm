"""Add webhook_url, webhook_set, last_health_check to tenants.

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-03-09 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "x9y0z1a2b3c4"
down_revision = "w8x9y0z1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("webhook_url", sa.String(512), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "webhook_set",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("last_health_check", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "last_health_check")
    op.drop_column("tenants", "webhook_set")
    op.drop_column("tenants", "webhook_url")
