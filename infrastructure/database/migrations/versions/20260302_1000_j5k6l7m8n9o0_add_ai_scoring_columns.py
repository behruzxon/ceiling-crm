"""add lead_temperature and closing_confidence to ai_conversations

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-03-02 10:00:00.000000

Changes
-------
ai_conversations table:
  + lead_temperature   VARCHAR(10)        NULLABLE
      Stores the latest AI-assessed lead temperature ("hot" | "warm" | "cold").
  + closing_confidence DOUBLE PRECISION   NULLABLE
      Stores the latest AI-assessed closing confidence score (0.0 – 1.0).

Both columns are nullable so existing rows and partial AI responses are unaffected.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j5k6l7m8n9o0"
down_revision = "i4j5k6l7m8n9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_conversations",
        sa.Column("lead_temperature", sa.String(10), nullable=True),
    )
    op.add_column(
        "ai_conversations",
        sa.Column("closing_confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_conversations", "closing_confidence")
    op.drop_column("ai_conversations", "lead_temperature")
