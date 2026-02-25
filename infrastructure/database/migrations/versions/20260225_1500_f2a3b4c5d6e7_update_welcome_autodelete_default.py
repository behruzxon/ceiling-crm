"""update welcome_autodelete_seconds default to 3600

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-25 15:00:00.000000

Changes the column DEFAULT from 45 s to 3600 s (1 hour).
Existing rows are NOT updated — only new groups created after this
migration will receive the 1-hour default.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "group_settings",
        "welcome_autodelete_seconds",
        server_default="3600",
    )


def downgrade() -> None:
    op.alter_column(
        "group_settings",
        "welcome_autodelete_seconds",
        server_default="45",
    )
