"""Add scheduled_followups table for 10-min follow-up engine.

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-05-25 12:00:00.000000+00:00
"""

revision = "v7w8x9y0z1a2"
down_revision = "u6v7w8x9y0z1"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "scheduled_followups",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("followup_type", sa.String(50), nullable=False),
        sa.Column("trigger_event_type", sa.String(50), nullable=False),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("message_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_fu_user_status", "scheduled_followups", ["telegram_user_id", "status"])
    # Partial index for Postgres only; harmless no-op if DB doesn't support it.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fu_pending "
        "ON scheduled_followups (scheduled_at) "
        "WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_fu_pending")
    op.drop_index("ix_fu_user_status", table_name="scheduled_followups")
    op.drop_table("scheduled_followups")
