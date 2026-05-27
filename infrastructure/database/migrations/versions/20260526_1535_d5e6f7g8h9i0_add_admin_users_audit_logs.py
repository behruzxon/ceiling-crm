"""add admin_users and admin_audit_logs
Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
"""
import sqlalchemy as sa
from alembic import op

revision = "d5e6f7g8h9i0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("admin_users",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("admin_id", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("role", sa.String(20), server_default="viewer"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_super_owner", sa.Boolean, server_default=sa.text("false")),
        sa.Column("permissions_override_json", sa.JSON, nullable=True),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_user_role", "admin_users", ["role"])
    op.create_index("ix_admin_user_active", "admin_users", ["is_active"])
    op.create_table("admin_audit_logs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("actor_admin_id", sa.String(100), nullable=True),
        sa.Column("actor_role", sa.String(20), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_admin_audit_actor", "admin_audit_logs", ["actor_admin_id", "created_at"])
    op.create_index("ix_admin_audit_action", "admin_audit_logs", ["action", "created_at"])
    op.create_index("ix_admin_audit_status", "admin_audit_logs", ["status", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_admin_audit_status", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_actor", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_index("ix_admin_user_active", table_name="admin_users")
    op.drop_index("ix_admin_user_role", table_name="admin_users")
    op.drop_table("admin_users")
