"""add lead_source web and chat values

Revision ID: c5d6e7f8g9h0
Revises: b4c5d6e7f8g9
Create Date: 2026-03-09 22:00:00.000000

PostgreSQL cannot remove enum values once added, so the downgrade is a no-op.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "c5d6e7f8g9h0"
down_revision = "b4c5d6e7f8g9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_source ADD VALUE IF NOT EXISTS 'web'")
    op.execute("ALTER TYPE lead_source ADD VALUE IF NOT EXISTS 'chat'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # To reverse: recreate the enum without 'web'/'chat' and ALTER the column.
    pass
