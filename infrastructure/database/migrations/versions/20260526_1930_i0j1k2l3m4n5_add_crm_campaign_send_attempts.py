"""add crm_campaign_send_attempts
Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
"""

import sqlalchemy as sa
from alembic import op

revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_campaign_send_attempts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("campaign_id", sa.BigInteger, nullable=False),
        sa.Column("contact_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_chat_id_hash", sa.String(128), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), server_default="telegram"),
        sa.Column("message_hash", sa.String(64), nullable=True),
        sa.Column("message_preview", sa.Text, nullable=True),
        sa.Column("blocked_reason", sa.String(200), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger, nullable=True),
        sa.Column("batch_id", sa.String(50), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index(
        "ix_send_campaign_created", "crm_campaign_send_attempts", ["campaign_id", "created_at"]
    )
    op.create_index(
        "ix_send_campaign_status", "crm_campaign_send_attempts", ["campaign_id", "status"]
    )
    op.create_index(
        "ix_send_contact_created", "crm_campaign_send_attempts", ["contact_id", "created_at"]
    )
    op.create_index("ix_send_batch", "crm_campaign_send_attempts", ["batch_id"])
    op.create_index(
        "ix_send_status_created", "crm_campaign_send_attempts", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_send_status_created", table_name="crm_campaign_send_attempts")
    op.drop_index("ix_send_batch", table_name="crm_campaign_send_attempts")
    op.drop_index("ix_send_contact_created", table_name="crm_campaign_send_attempts")
    op.drop_index("ix_send_campaign_status", table_name="crm_campaign_send_attempts")
    op.drop_index("ix_send_campaign_created", table_name="crm_campaign_send_attempts")
    op.drop_table("crm_campaign_send_attempts")
