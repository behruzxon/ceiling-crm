"""add agent_execution_records table

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-05-26 05:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_execution_records",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("execution_id", sa.String(36), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("payload_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("result_json", sa.JSON, nullable=True),
        sa.Column("trace_json", sa.JSON, nullable=True),
        sa.Column("message_text_hash", sa.String(64), nullable=True),
        sa.Column("approved_by", sa.BigInteger, nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.BigInteger, nullable=True),
        sa.Column("rejected_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(255), nullable=True),
        sa.Column("blocked_reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_exec_user_created",
        "agent_execution_records",
        ["telegram_user_id", "created_at"],
    )
    op.create_index(
        "ix_exec_status_expires",
        "agent_execution_records",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_exec_mode_status",
        "agent_execution_records",
        ["mode", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_exec_mode_status", table_name="agent_execution_records")
    op.drop_index("ix_exec_status_expires", table_name="agent_execution_records")
    op.drop_index("ix_exec_user_created", table_name="agent_execution_records")
    op.drop_table("agent_execution_records")
