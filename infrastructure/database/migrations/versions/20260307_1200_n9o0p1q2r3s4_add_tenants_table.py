"""Add tenants table and tenant_id FK to all existing tables.

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-03-07 12:00:00.000000

Phase 0 of the SaaS migration.  Introduces the ``tenants`` table that will
store per-business configuration (bot token, AI prompt, pricing, etc.) and
adds a **nullable** ``tenant_id`` FK column to every existing data table.

Nullable so that the current bot continues to work without any code changes.
The seed script (``scripts/seed_db.py``) will create a default tenant and
backfill all existing rows.

Tables modified (17):
  users, leads, groups, admin_groups, ai_user_memory, ai_conversations,
  broadcasts, pipeline_stages, payments, quotes, appointments, audit_logs,
  blocked_chats, group_settings, group_join_events, lead_actions, warranties
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "n9o0p1q2r3s4"
down_revision = "m8n9o0p1q2r3"
branch_labels = None
depends_on = None

# All tables that receive a tenant_id column.
_TABLES = [
    "users",
    "leads",
    "groups",
    "admin_groups",
    "ai_user_memory",
    "ai_conversations",
    "broadcasts",
    "pipeline_stages",
    "payments",
    "quotes",
    "appointments",
    "audit_logs",
    "blocked_chats",
    "group_settings",
    "group_join_events",
    "lead_actions",
    "warranties",
]


def upgrade() -> None:
    # ── 1. Create tenants table ────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        # Bot credentials
        sa.Column("bot_token", sa.String(256), nullable=True),
        sa.Column("bot_username", sa.String(64), nullable=True),
        # Telegram group/user IDs
        sa.Column("admin_group_id", sa.BigInteger, nullable=True),
        sa.Column("main_group_id", sa.BigInteger, nullable=True),
        sa.Column("admin_user_id", sa.BigInteger, nullable=True),
        # AI configuration
        sa.Column("ai_system_prompt", sa.Text, nullable=True),
        sa.Column("knowledge_base", sa.Text, nullable=True),
        # Business configuration (JSON)
        sa.Column("pricing_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("menu_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("social_links", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("districts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        # Status
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        # Timestamps
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"])

    # ── 2. Add nullable tenant_id FK + index to every existing table ───────
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", sa.BigInteger, nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def downgrade() -> None:
    # ── Remove tenant_id from all tables (reverse order) ───────────────────
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    # ── Drop tenants table ─────────────────────────────────────────────────
    op.drop_index("ix_tenants_is_active", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
