"""add admin_sessions and admin_login_attempts
Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
"""
import sqlalchemy as sa
from alembic import op

revision = "e6f7g8h9i0j1"
down_revision = "d5e6f7g8h9i0"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("admin_sessions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("session_id_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("admin_id", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_admin_session_admin_created", "admin_sessions", ["admin_id", "created_at"])
    op.create_index("ix_admin_session_status_expires", "admin_sessions", ["status", "expires_at"])
    op.create_index("ix_admin_session_last_seen", "admin_sessions", ["last_seen_at"])
    op.create_table("admin_login_attempts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("admin_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_admin_login_admin_created", "admin_login_attempts", ["admin_id", "created_at"])
    op.create_index("ix_admin_login_ip_created", "admin_login_attempts", ["ip_address", "created_at"])
    op.create_index("ix_admin_login_status_created", "admin_login_attempts", ["status", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_admin_login_status_created", table_name="admin_login_attempts")
    op.drop_index("ix_admin_login_ip_created", table_name="admin_login_attempts")
    op.drop_index("ix_admin_login_admin_created", table_name="admin_login_attempts")
    op.drop_table("admin_login_attempts")
    op.drop_index("ix_admin_session_last_seen", table_name="admin_sessions")
    op.drop_index("ix_admin_session_status_expires", table_name="admin_sessions")
    op.drop_index("ix_admin_session_admin_created", table_name="admin_sessions")
    op.drop_table("admin_sessions")
