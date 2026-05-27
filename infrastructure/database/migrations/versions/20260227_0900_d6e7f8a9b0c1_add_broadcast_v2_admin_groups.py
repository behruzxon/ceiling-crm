"""add broadcast_v2 columns, admin_groups table, and new enum values

Revision ID: d6e7f8a9b0c1
Revises: c3d4e5f6a1b2
Create Date: 2026-02-27 09:00:00.000000

Changes:
- broadcast_status enum: add 'pending', 'cancelled'
- New enum types: segment_type, payload_type
- broadcasts: add segment_type, lead_stage, payload_type, text, file_id,
              total, finished_at columns
- New table: admin_groups (chat_id PK, title, added_at)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c3d4e5f6a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Extend broadcast_status enum ──────────────────────────────────────
    op.execute(sa.text("ALTER TYPE broadcast_status ADD VALUE IF NOT EXISTS 'pending'"))
    op.execute(sa.text("ALTER TYPE broadcast_status ADD VALUE IF NOT EXISTS 'cancelled'"))

    # ── 2. Create new enum types ──────────────────────────────────────────────
    segment_type = sa.Enum(
        "all_private",
        "lead_stage",
        "admin_groups",
        name="segment_type",
    )
    payload_type = sa.Enum(
        "text",
        "photo",
        "video",
        "document",
        name="payload_type",
    )
    segment_type.create(op.get_bind(), checkfirst=True)
    payload_type.create(op.get_bind(), checkfirst=True)

    # ── 3. Add new columns to broadcasts ─────────────────────────────────────
    op.add_column(
        "broadcasts",
        sa.Column(
            "segment_type",
            sa.Enum("all_private", "lead_stage", "admin_groups", name="segment_type"),
            nullable=False,
            server_default="all_private",
        ),
    )
    op.add_column(
        "broadcasts",
        sa.Column("lead_stage", sa.String(32), nullable=True),
    )
    op.add_column(
        "broadcasts",
        sa.Column(
            "payload_type",
            sa.Enum("text", "photo", "video", "document", name="payload_type"),
            nullable=False,
            server_default="text",
        ),
    )
    op.add_column(
        "broadcasts",
        sa.Column("text", sa.Text, nullable=True),
    )
    op.add_column(
        "broadcasts",
        sa.Column("file_id", sa.String(512), nullable=True),
    )
    op.add_column(
        "broadcasts",
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "broadcasts",
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # ── 4. Create admin_groups table ─────────────────────────────────────────
    op.create_table(
        "admin_groups",
        sa.Column("chat_id", sa.BigInteger, primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_groups")

    op.drop_column("broadcasts", "finished_at")
    op.drop_column("broadcasts", "total")
    op.drop_column("broadcasts", "file_id")
    op.drop_column("broadcasts", "text")
    op.drop_column("broadcasts", "payload_type")
    op.drop_column("broadcasts", "lead_stage")
    op.drop_column("broadcasts", "segment_type")

    op.execute(sa.text("DROP TYPE IF EXISTS payload_type"))
    op.execute(sa.text("DROP TYPE IF EXISTS segment_type"))
    # broadcast_status enum values (pending, cancelled) cannot be removed in PostgreSQL.
