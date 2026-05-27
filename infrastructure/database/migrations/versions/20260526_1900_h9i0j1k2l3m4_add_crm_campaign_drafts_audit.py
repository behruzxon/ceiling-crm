"""add crm_campaign_drafts and crm_campaign_audit_logs
Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
"""

import sqlalchemy as sa
from alembic import op

revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_campaign_drafts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("segment_key", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("recipient_count", sa.Integer, server_default="0"),
        sa.Column("excluded_count", sa.Integer, server_default="0"),
        sa.Column("safety_status", sa.String(20), server_default="pending"),
        sa.Column("safety_reasons_json", sa.JSON, nullable=True),
        sa.Column("filters_json", sa.JSON, nullable=True),
        sa.Column("preview_recipients_json", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_campaign_segment", "crm_campaign_drafts", ["segment_key"])
    op.create_index("ix_campaign_status", "crm_campaign_drafts", ["status"])
    op.create_index("ix_campaign_created", "crm_campaign_drafts", ["created_at"])
    op.create_index("ix_campaign_created_by", "crm_campaign_drafts", ["created_by"])
    op.create_table(
        "crm_campaign_audit_logs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("campaign_id", sa.BigInteger, nullable=True),
        sa.Column("actor_admin_id", sa.String(100), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_camp_audit_campaign", "crm_campaign_audit_logs", ["campaign_id", "created_at"]
    )
    op.create_index(
        "ix_camp_audit_actor", "crm_campaign_audit_logs", ["actor_admin_id", "created_at"]
    )
    op.create_index("ix_camp_audit_action", "crm_campaign_audit_logs", ["action", "created_at"])
    op.create_index("ix_camp_audit_status", "crm_campaign_audit_logs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_camp_audit_status", table_name="crm_campaign_audit_logs")
    op.drop_index("ix_camp_audit_action", table_name="crm_campaign_audit_logs")
    op.drop_index("ix_camp_audit_actor", table_name="crm_campaign_audit_logs")
    op.drop_index("ix_camp_audit_campaign", table_name="crm_campaign_audit_logs")
    op.drop_table("crm_campaign_audit_logs")
    op.drop_index("ix_campaign_created_by", table_name="crm_campaign_drafts")
    op.drop_index("ix_campaign_created", table_name="crm_campaign_drafts")
    op.drop_index("ix_campaign_status", table_name="crm_campaign_drafts")
    op.drop_index("ix_campaign_segment", table_name="crm_campaign_drafts")
    op.drop_table("crm_campaign_drafts")
