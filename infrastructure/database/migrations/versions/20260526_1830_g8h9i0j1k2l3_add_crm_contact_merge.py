"""add crm contact merge fields and audit table
Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
"""
from alembic import op
import sqlalchemy as sa
revision = "g8h9i0j1k2l3"
down_revision = "f7g8h9i0j1k2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("crm_contacts", sa.Column("merged_into_contact_id", sa.BigInteger, nullable=True))
    op.add_column("crm_contacts", sa.Column("merged_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("crm_contacts", sa.Column("merge_status", sa.String(30), server_default="active"))
    op.add_column("crm_contacts", sa.Column("data_quality_score", sa.Integer, nullable=True))
    op.add_column("crm_contacts", sa.Column("duplicate_confidence", sa.Integer, nullable=True))
    op.add_column("crm_contacts", sa.Column("duplicate_reason", sa.String(200), nullable=True))
    op.create_index("ix_crm_contact_merged_into", "crm_contacts", ["merged_into_contact_id"])
    op.create_index("ix_crm_contact_merge_status", "crm_contacts", ["merge_status"])
    op.create_table("crm_contact_merge_audit",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("source_contact_id", sa.BigInteger, nullable=False),
        sa.Column("target_contact_id", sa.BigInteger, nullable=False),
        sa.Column("actor_admin_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Integer, nullable=True),
        sa.Column("reasons_json", sa.JSON, nullable=True),
        sa.Column("merge_plan_json", sa.JSON, nullable=True),
        sa.Column("before_source_json", sa.JSON, nullable=True),
        sa.Column("before_target_json", sa.JSON, nullable=True),
        sa.Column("result_json", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("merged_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_merge_audit_source", "crm_contact_merge_audit", ["source_contact_id"])
    op.create_index("ix_merge_audit_target", "crm_contact_merge_audit", ["target_contact_id"])
    op.create_index("ix_merge_audit_status", "crm_contact_merge_audit", ["status"])
    op.create_index("ix_merge_audit_created", "crm_contact_merge_audit", ["created_at"])

def downgrade() -> None:
    op.drop_index("ix_merge_audit_created", table_name="crm_contact_merge_audit")
    op.drop_index("ix_merge_audit_status", table_name="crm_contact_merge_audit")
    op.drop_index("ix_merge_audit_target", table_name="crm_contact_merge_audit")
    op.drop_index("ix_merge_audit_source", table_name="crm_contact_merge_audit")
    op.drop_table("crm_contact_merge_audit")
    op.drop_index("ix_crm_contact_merge_status", table_name="crm_contacts")
    op.drop_index("ix_crm_contact_merged_into", table_name="crm_contacts")
    op.drop_column("crm_contacts", "duplicate_reason")
    op.drop_column("crm_contacts", "duplicate_confidence")
    op.drop_column("crm_contacts", "data_quality_score")
    op.drop_column("crm_contacts", "merge_status")
    op.drop_column("crm_contacts", "merged_at")
    op.drop_column("crm_contacts", "merged_into_contact_id")
