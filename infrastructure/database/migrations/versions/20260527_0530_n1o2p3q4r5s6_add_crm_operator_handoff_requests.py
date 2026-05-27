"""add crm_operator_handoff_requests

Revision ID: n1o2p3q4r5s6
Revises: i0j1k2l3m4n5
Create Date: 2026-05-27 05:30:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n1o2p3q4r5s6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_operator_handoff_requests",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contact_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("source", sa.String(30), nullable=False, server_default="bot"),
        sa.Column("reason", sa.String(50), nullable=True),
        sa.Column("user_message_preview", sa.Text, nullable=True),
        sa.Column("phone_masked", sa.String(30), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("area_m2", sa.Float, nullable=True),
        sa.Column("ceiling_type", sa.String(50), nullable=True),
        sa.Column("assigned_to_admin_id", sa.String(50), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("contacted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index(
        "ix_handoff_contact_status", "crm_operator_handoff_requests", ["contact_id", "status"]
    )
    op.create_index(
        "ix_handoff_status_priority_created",
        "crm_operator_handoff_requests",
        ["status", "priority", "created_at"],
    )
    op.create_index(
        "ix_handoff_tg_user_status", "crm_operator_handoff_requests", ["telegram_user_id", "status"]
    )
    op.create_index("ix_handoff_created", "crm_operator_handoff_requests", ["created_at"])
    op.create_index(
        "ix_handoff_assigned_status",
        "crm_operator_handoff_requests",
        ["assigned_to_admin_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("crm_operator_handoff_requests")
