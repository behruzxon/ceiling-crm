"""add admin_ip_access_rules
Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
"""
from alembic import op
import sqlalchemy as sa
revision = "f7g8h9i0j1k2"
down_revision = "e6f7g8h9i0j1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("admin_ip_access_rules",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("ip_pattern", sa.String(100), nullable=False),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_ip_rule_pattern", "admin_ip_access_rules", ["ip_pattern"])
    op.create_index("ix_ip_rule_type", "admin_ip_access_rules", ["rule_type"])
    op.create_index("ix_ip_rule_active", "admin_ip_access_rules", ["is_active"])
    op.create_index("ix_ip_rule_created", "admin_ip_access_rules", ["created_at"])

def downgrade() -> None:
    op.drop_index("ix_ip_rule_created", table_name="admin_ip_access_rules")
    op.drop_index("ix_ip_rule_active", table_name="admin_ip_access_rules")
    op.drop_index("ix_ip_rule_type", table_name="admin_ip_access_rules")
    op.drop_index("ix_ip_rule_pattern", table_name="admin_ip_access_rules")
    op.drop_table("admin_ip_access_rules")
