"""add package columns to leads + PACKAGE_SELECTED pipeline stage

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-02-27 20:00:00.000000

Changes
-------
1. ALTER TYPE pipeline_stage ADD VALUE 'PACKAGE_SELECTED'
   — New funnel entry stage for the "Tayyor paketlar" feature.
   — Inserted between NEW and CONTACTED in the value list (no ordering
     enforced by the DB; placement is for documentation only).

2. leads table — four new columns:
   package_type  VARCHAR(16) NULL   — standard / premium / vip
   lead_status   VARCHAR(16) NULL   — hot / warm / cold
   last_action   VARCHAR(64) NULL   — latest funnel action (e.g. "package_order")
   score         INTEGER NOT NULL DEFAULT 0

3. New indexes:
   ix_leads_user_id      ON leads(user_id)       — accelerates per-user queries
   ix_leads_package_type ON leads(package_type)  — segment queries
   ix_leads_lead_status  ON leads(lead_status)   — hot-lead dashboards
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "g2h3i4j5k6l7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Add PACKAGE_SELECTED to the pipeline_stage enum ───────────────────
    # The pipeline_stage type was created in a previous transaction so
    # ADD VALUE is safe inside this transaction on PostgreSQL 12+.
    op.execute(
        sa.text("ALTER TYPE pipeline_stage ADD VALUE IF NOT EXISTS 'PACKAGE_SELECTED'")
    )

    # ── 2. New columns on leads ───────────────────────────────────────────────
    op.add_column(
        "leads",
        sa.Column("package_type", sa.String(16), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("lead_status", sa.String(16), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("last_action", sa.String(64), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
    )

    # ── 3. Indexes ────────────────────────────────────────────────────────────
    op.create_index("ix_leads_user_id", "leads", ["user_id"])
    op.create_index("ix_leads_package_type", "leads", ["package_type"])
    op.create_index("ix_leads_lead_status", "leads", ["lead_status"])


def downgrade() -> None:
    op.drop_index("ix_leads_lead_status", table_name="leads")
    op.drop_index("ix_leads_package_type", table_name="leads")
    op.drop_index("ix_leads_user_id", table_name="leads")
    op.drop_column("leads", "score")
    op.drop_column("leads", "last_action")
    op.drop_column("leads", "lead_status")
    op.drop_column("leads", "package_type")
    # Note: PostgreSQL does not support removing enum values; PACKAGE_SELECTED
    # remains in the pipeline_stage type after downgrade.
