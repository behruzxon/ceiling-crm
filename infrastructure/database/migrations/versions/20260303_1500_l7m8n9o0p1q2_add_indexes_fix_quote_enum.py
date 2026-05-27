"""Add missing DB indexes and fix ceiling_category_quotes enum serialization.

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-03-03 15:00:00.000000

Changes
-------
1. pipeline_stages: add composite index (lead_id, created_at)
   — eliminates full table scan in _latest_stage_subquery(), which is
     called on every lead list / kanban query.

2. users: add index on username
   — speeds up get_by_username() used in admin user-lookup flows.

3. users: add index on role
   — speeds up get_by_role() used in broadcast segment queries.

4. quotes.category: fix enum serialization
   — Without values_callable, SQLAlchemy stored UPPERCASE names (e.g. "GULLI")
     instead of lowercase values (e.g. "gulli"), matching the same bug that
     was fixed for BroadcastModel in migration e7f8a9b0c1d2.
   — Strategy: TEXT intermediate → lowercase data → recreate type → cast back.
   — Safe to re-run: LOWER('gulli') = 'gulli' (idempotent).
"""
from __future__ import annotations

from alembic import op

revision = "l7m8n9o0p1q2"
down_revision = "k6l7m8n9o0p1"
branch_labels = None
depends_on = None

# CeilingCategory values (must match shared/constants/enums.py)
_CATEGORY_VALUES = (
    "gulli", "odnotonny", "mramor", "qora_naqsh_uf",
    "hi_tech", "kosmos", "osmon", "oshxona", "naqsh_ramka", "naqsh_oq",
)


def upgrade() -> None:
    # ── 1. pipeline_stages composite index ───────────────────────────────────
    op.create_index(
        "ix_pipeline_stages_lead_created",
        "pipeline_stages",
        ["lead_id", "created_at"],
    )

    # ── 2. users.username index ───────────────────────────────────────────────
    op.create_index("ix_users_username", "users", ["username"])

    # ── 3. users.role index ───────────────────────────────────────────────────
    op.create_index("ix_users_role", "users", ["role"])

    # ── 4. Fix quotes.category enum ───────────────────────────────────────────
    # Step 4a: detach column from the (potentially broken) enum type
    op.execute(
        "ALTER TABLE quotes ALTER COLUMN category TYPE TEXT USING category::TEXT"
    )
    # Step 4b: normalise any existing uppercase values to lowercase
    op.execute("UPDATE quotes SET category = LOWER(category)")
    # Step 4c: drop the old enum type (may have uppercase member names)
    op.execute("DROP TYPE IF EXISTS ceiling_category_quotes")
    # Step 4d: recreate with correct lowercase values
    vals = ", ".join(f"'{v}'" for v in _CATEGORY_VALUES)
    op.execute(f"CREATE TYPE ceiling_category_quotes AS ENUM ({vals})")
    # Step 4e: cast TEXT column back to the corrected enum
    op.execute(
        "ALTER TABLE quotes "
        "ALTER COLUMN category TYPE ceiling_category_quotes "
        "USING category::ceiling_category_quotes"
    )


def downgrade() -> None:
    # ── 4. Revert quotes.category (no data loss — values stay lowercase) ──────
    # Just drop and recreate without values_callable constraint differences;
    # the Python model change is what actually matters for correctness.
    op.execute(
        "ALTER TABLE quotes ALTER COLUMN category TYPE TEXT USING category::TEXT"
    )
    op.execute("DROP TYPE IF EXISTS ceiling_category_quotes")
    vals = ", ".join(f"'{v}'" for v in _CATEGORY_VALUES)
    op.execute(f"CREATE TYPE ceiling_category_quotes AS ENUM ({vals})")
    op.execute(
        "ALTER TABLE quotes "
        "ALTER COLUMN category TYPE ceiling_category_quotes "
        "USING category::ceiling_category_quotes"
    )

    # ── 3. Drop users.role index ──────────────────────────────────────────────
    op.drop_index("ix_users_role", table_name="users")

    # ── 2. Drop users.username index ─────────────────────────────────────────
    op.drop_index("ix_users_username", table_name="users")

    # ── 1. Drop pipeline_stages index ────────────────────────────────────────
    op.drop_index("ix_pipeline_stages_lead_created", table_name="pipeline_stages")
