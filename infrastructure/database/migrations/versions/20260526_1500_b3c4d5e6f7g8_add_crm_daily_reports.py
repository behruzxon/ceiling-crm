"""add crm_daily_reports
Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
"""
import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7g8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "crm_daily_reports",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("report_date", sa.Date, nullable=False, unique=True),
        sa.Column("period_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), server_default="generated"),
        sa.Column("delivery_mode", sa.String(20), server_default="disabled"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("recommendations_json", sa.JSON, nullable=True),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_daily_report_status", "crm_daily_reports", ["status"])

def downgrade() -> None:
    op.drop_index("ix_daily_report_status", table_name="crm_daily_reports")
    op.drop_table("crm_daily_reports")
