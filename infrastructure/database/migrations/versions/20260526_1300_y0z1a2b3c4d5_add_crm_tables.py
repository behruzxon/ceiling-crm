"""add crm_contacts, crm_messages, crm_contact_notes, crm_contact_tags

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-05-26 13:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "y0z1a2b3c4d5"
down_revision = "x9y0z1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True, unique=True),
        sa.Column("telegram_chat_id", sa.BigInteger, nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True),
        sa.Column("source", sa.String(30), nullable=True),
        sa.Column("lead_status", sa.String(30), server_default="new"),
        sa.Column("lead_score", sa.Integer, server_default="0"),
        sa.Column("temperature", sa.String(10), nullable=True),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_crm_contact_status", "crm_contacts", ["lead_status"])
    op.create_index("ix_crm_contact_temp", "crm_contacts", ["temperature"])
    op.create_index("ix_crm_contact_last_msg", "crm_contacts", ["last_message_at"])

    op.create_table(
        "crm_messages",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger, nullable=True),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("sender_type", sa.String(20), nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("message_type", sa.String(20), server_default="text"),
        sa.Column("payload_json", sa.JSON, nullable=True),
        sa.Column("redacted_text", sa.Text, nullable=True),
        sa.Column("is_sensitive", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_crm_msg_contact_created", "crm_messages", ["contact_id", "created_at"])
    op.create_index("ix_crm_msg_user_created", "crm_messages", ["telegram_user_id", "created_at"])
    op.create_index("ix_crm_msg_direction", "crm_messages", ["direction"])

    op.create_table(
        "crm_contact_notes",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger, nullable=False),
        sa.Column("note_text", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "crm_contact_tags",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger, nullable=False),
        sa.Column("tag", sa.String(30), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("contact_id", "tag", name="uq_contact_tag"),
    )


def downgrade() -> None:
    op.drop_table("crm_contact_tags")
    op.drop_table("crm_contact_notes")
    op.drop_index("ix_crm_msg_direction", table_name="crm_messages")
    op.drop_index("ix_crm_msg_user_created", table_name="crm_messages")
    op.drop_index("ix_crm_msg_contact_created", table_name="crm_messages")
    op.drop_table("crm_messages")
    op.drop_index("ix_crm_contact_last_msg", table_name="crm_contacts")
    op.drop_index("ix_crm_contact_temp", table_name="crm_contacts")
    op.drop_index("ix_crm_contact_status", table_name="crm_contacts")
    op.drop_table("crm_contacts")
