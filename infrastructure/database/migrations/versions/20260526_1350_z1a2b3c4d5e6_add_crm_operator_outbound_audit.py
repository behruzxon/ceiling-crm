"""add crm_operator_outbound_audit
Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
"""
import sqlalchemy as sa
from alembic import op

revision = "z1a2b3c4d5e6"
down_revision = "y0z1a2b3c4d5"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "crm_operator_outbound_audit",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger, nullable=True),
        sa.Column("operator_id", sa.String(50), nullable=True),
        sa.Column("message_hash", sa.String(64), nullable=False),
        sa.Column("message_preview", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("blocked_reason", sa.String(255), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_crm_audit_contact", "crm_operator_outbound_audit", ["contact_id", "created_at"])
    op.create_index("ix_crm_audit_status", "crm_operator_outbound_audit", ["status", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_crm_audit_status", table_name="crm_operator_outbound_audit")
    op.drop_index("ix_crm_audit_contact", table_name="crm_operator_outbound_audit")
    op.drop_table("crm_operator_outbound_audit")
