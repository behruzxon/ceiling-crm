"""add crm_operator_tasks
Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
"""
import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "crm_operator_tasks",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="todo"),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("snoozed_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("assigned_to", sa.String(50), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_task_contact_status", "crm_operator_tasks", ["contact_id", "status"])
    op.create_index("ix_task_status_due", "crm_operator_tasks", ["status", "due_at"])
    op.create_index("ix_task_priority_due", "crm_operator_tasks", ["priority", "due_at"])

def downgrade() -> None:
    op.drop_index("ix_task_priority_due", table_name="crm_operator_tasks")
    op.drop_index("ix_task_status_due", table_name="crm_operator_tasks")
    op.drop_index("ix_task_contact_status", table_name="crm_operator_tasks")
    op.drop_table("crm_operator_tasks")
