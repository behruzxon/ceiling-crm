"""Add tenant_ai_knowledge table.

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-03-09 12:00:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "v7w8x9y0z1a2"
down_revision: str = "u6v7w8x9y0z1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_ai_knowledge",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
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

    op.create_index(
        "ix_tenant_ai_knowledge_tenant_id",
        "tenant_ai_knowledge",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tenant_ai_knowledge_category",
        "tenant_ai_knowledge",
        ["tenant_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_ai_knowledge_category", table_name="tenant_ai_knowledge")
    op.drop_index("ix_tenant_ai_knowledge_tenant_id", table_name="tenant_ai_knowledge")
    op.drop_table("tenant_ai_knowledge")
