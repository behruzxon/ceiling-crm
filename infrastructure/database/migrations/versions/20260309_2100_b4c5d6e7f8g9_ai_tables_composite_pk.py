"""Convert ai_conversations and ai_user_memory to composite PK (tenant_id, user_id).

Fixes cross-tenant memory collision: in a multi-tenant SaaS, the same
Telegram user_id can exist across different tenants.  A single-column PK
on user_id causes data overwrites.

Migration steps (per table):
  1. Drop the old single-column PK on user_id
  2. Create the new composite PK on (tenant_id, user_id)
  3. Add an index on user_id for reverse lookups

Precondition: tenant_id is already NOT NULL on both tables
(ensured by migration t5u6v7w8x9y0).

Revision ID: b4c5d6e7f8g9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-09 21:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8g9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ai_conversations ───────────────────────────────────────────────────
    # 1. Drop old single-column PK
    op.drop_constraint("ai_conversations_pkey", "ai_conversations", type_="primary")
    # 2. Create composite PK
    op.create_primary_key(
        "ai_conversations_pkey", "ai_conversations", ["tenant_id", "user_id"]
    )
    # 3. Index on user_id for reverse lookups
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])

    # ── ai_user_memory ─────────────────────────────────────────────────────
    # 1. Drop old single-column PK
    op.drop_constraint("ai_user_memory_pkey", "ai_user_memory", type_="primary")
    # 2. Create composite PK
    op.create_primary_key(
        "ai_user_memory_pkey", "ai_user_memory", ["tenant_id", "user_id"]
    )
    # 3. Index on user_id for reverse lookups
    op.create_index("ix_ai_user_memory_user_id", "ai_user_memory", ["user_id"])


def downgrade() -> None:
    # ── ai_user_memory ─────────────────────────────────────────────────────
    op.drop_index("ix_ai_user_memory_user_id", "ai_user_memory")
    op.drop_constraint("ai_user_memory_pkey", "ai_user_memory", type_="primary")
    op.create_primary_key("ai_user_memory_pkey", "ai_user_memory", ["user_id"])

    # ── ai_conversations ───────────────────────────────────────────────────
    op.drop_index("ix_ai_conversations_user_id", "ai_conversations")
    op.drop_constraint("ai_conversations_pkey", "ai_conversations", type_="primary")
    op.create_primary_key("ai_conversations_pkey", "ai_conversations", ["user_id"])
