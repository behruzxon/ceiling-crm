"""add agent_runtime_settings and agent_setting_audit_logs

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-05-26 06:50:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "x9y0z1a2b3c4"
down_revision = "w8x9y0z1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runtime_settings",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("value_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("value_type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(30), server_default="control_center"),
        sa.Column("risk_level", sa.String(20), server_default="low"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.BigInteger, nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )
    op.create_index("ix_runtime_setting_active", "agent_runtime_settings", ["is_active"])

    op.create_table(
        "agent_setting_audit_logs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("setting_key", sa.String(100), nullable=False),
        sa.Column("old_value_json", sa.JSON, nullable=True),
        sa.Column("new_value_json", sa.JSON, nullable=True),
        sa.Column("changed_by", sa.BigInteger, nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("confirmation_token_hash", sa.String(64), nullable=True),
        sa.Column("rollback_snapshot_json", sa.JSON, nullable=True),
        sa.Column("validation_result_json", sa.JSON, nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_key_created", "agent_setting_audit_logs",
                    ["setting_key", "created_at"])
    op.create_index("ix_audit_action_created", "agent_setting_audit_logs",
                    ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_action_created", table_name="agent_setting_audit_logs")
    op.drop_index("ix_audit_key_created", table_name="agent_setting_audit_logs")
    op.drop_table("agent_setting_audit_logs")
    op.drop_index("ix_runtime_setting_active", table_name="agent_runtime_settings")
    op.drop_table("agent_runtime_settings")
