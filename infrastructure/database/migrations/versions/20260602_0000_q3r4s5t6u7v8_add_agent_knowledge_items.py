"""add agent_knowledge_items

Admin-editable knowledge base (FAQ / price / catalog / warranty / objection /
service_area / process / other). Items can be authored manually or promoted from
an Unknown Question. This is the storage + CRUD foundation only — the bot does
NOT read these items yet (see doc 156, "Option A"). Additive, no destructive ops.

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-06-02 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_knowledge_items",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("title", sa.Text, nullable=False, server_default=""),
        sa.Column("question", sa.Text, nullable=False, server_default=""),
        sa.Column("answer", sa.Text, nullable=False, server_default=""),
        sa.Column("category", sa.String(30), nullable=False, server_default="faq"),
        sa.Column("language", sa.String(8), nullable=False, server_default="uz"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("source_unknown_question_id", sa.BigInteger, nullable=True),
        sa.Column("aliases_json", sa.JSON, nullable=True),
        sa.Column("tags_json", sa.JSON, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.Column("approved_by", sa.String(50), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_kb_status", "agent_knowledge_items", ["status"])
    op.create_index("ix_kb_category", "agent_knowledge_items", ["category"])
    op.create_index("ix_kb_language", "agent_knowledge_items", ["language"])
    op.create_index("ix_kb_source_uq", "agent_knowledge_items", ["source_unknown_question_id"])
    op.create_index("ix_kb_created", "agent_knowledge_items", ["created_at"])
    op.create_index("ix_kb_priority", "agent_knowledge_items", ["priority"])
    op.create_index(
        "ix_kb_status_category_lang",
        "agent_knowledge_items",
        ["status", "category", "language"],
    )


def downgrade() -> None:
    op.drop_table("agent_knowledge_items")
