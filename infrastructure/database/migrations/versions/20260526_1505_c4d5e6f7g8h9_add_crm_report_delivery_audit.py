"""add crm_report_delivery_audit
Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
"""
from alembic import op
import sqlalchemy as sa
revision = "c4d5e6f7g8h9"
down_revision = "b3c4d5e6f7g8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "crm_report_delivery_audit",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("report_id", sa.BigInteger, nullable=False),
        sa.Column("delivery_channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("approved_by", sa.String(50), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.String(50), nullable=True),
        sa.Column("rejected_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("recipient_hash", sa.String(64), nullable=True),
        sa.Column("message_preview", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_delivery_audit_report", "crm_report_delivery_audit", ["report_id", "created_at"])
    op.create_index("ix_delivery_audit_status", "crm_report_delivery_audit", ["status", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_delivery_audit_status", table_name="crm_report_delivery_audit")
    op.drop_index("ix_delivery_audit_report", table_name="crm_report_delivery_audit")
    op.drop_table("crm_report_delivery_audit")
