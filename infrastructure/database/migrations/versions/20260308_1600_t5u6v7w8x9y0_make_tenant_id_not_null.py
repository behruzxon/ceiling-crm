"""Make tenant_id NOT NULL on all tenant-owned tables.

Precondition: seed_db.py must have been run to backfill all existing rows
with a valid tenant_id. The migration checks for NULL values first and
raises a clear error if any are found.

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-03-08 16:00:00.000000+00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t5u6v7w8x9y0"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None

# All 17 tables that received nullable tenant_id in n9o0p1q2r3s4
_TABLES = [
    "users",
    "leads",
    "lead_actions",
    "payments",
    "appointments",
    "quotes",
    "broadcasts",
    "groups",
    "group_join_events",
    "group_settings",
    "admin_groups",
    "blocked_chats",
    "audit_logs",
    "ai_conversations",
    "ai_user_memory",
    "pipeline_stages",
    "warranties",
]


def upgrade() -> None:
    # ── Precondition: verify no NULL tenant_ids remain ────────────────
    conn = op.get_bind()
    failures: list[str] = []
    for table in _TABLES:
        result = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL")  # noqa: S608
        )
        null_count = result.scalar()
        if null_count:
            failures.append(f"  {table}: {null_count} rows with NULL tenant_id")

    if failures:
        detail = "\n".join(failures)
        raise RuntimeError(
            f"Cannot make tenant_id NOT NULL — found NULL values:\n{detail}\n\n"
            "Run `python scripts/seed_db.py` to backfill tenant_id first."
        )

    # ── Alter columns to NOT NULL ─────────────────────────────────────
    for table in _TABLES:
        op.alter_column(
            table,
            "tenant_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "tenant_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )
