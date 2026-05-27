"""replace_ceiling_category_enum

Replace the old 10-member ceiling_category PostgreSQL enum type with a new
10-member set that reflects the current product catalogue.

Old values → new values mapping
---------------------------------
  matviy_oq      → odnotonny
  yaltiroq_oq    → odnotonny
  qora_premium   → qora_naqsh_uf
  gulli_3d       → gulli
  mramor_dizayn  → mramor
  led_podsvetka  → hi_tech
  yulduzli_osmon → kosmos
  ikki_darajali  → odnotonny
  ofis_minimal   → odnotonny
  oshxona        → oshxona        (unchanged)

Strategy (TEXT intermediate)
------------------------------
  1. CREATE the new enum type alongside the old one.
  2. ALTER leads.category to TEXT so Postgres has no type dependency.
  3. UPDATE rows: remap every old value to the nearest new value.
  4. ALTER leads.category back to the new enum type via USING cast.
  5. DROP the old type.
  6. RENAME the new type to take the original name.

The groups table has its own separate enum type (ceiling_category_groups)
and is NOT touched by this migration.

Revision ID: d5e8f1a2b3c4
Revises: c4f8a1e2d3b5
Create Date: 2026-02-20 21:15:00.000000+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5e8f1a2b3c4'
down_revision: str | None = 'c4f8a1e2d3b5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New enum values (upgrade target)
_NEW_VALUES = (
    'gulli', 'odnotonny', 'mramor', 'qora_naqsh_uf',
    'hi_tech', 'kosmos', 'osmon', 'oshxona', 'naqsh_ramka', 'naqsh_oq',
)

# Old enum values (downgrade target)
_OLD_VALUES = (
    'matviy_oq', 'yaltiroq_oq', 'qora_premium', 'gulli_3d',
    'mramor_dizayn', 'led_podsvetka', 'yulduzli_osmon',
    'ikki_darajali', 'ofis_minimal', 'oshxona',
)


def upgrade() -> None:
    # ── 1. Create new enum type alongside the old one ─────────────────────────
    new_vals = ", ".join(f"'{v}'" for v in _NEW_VALUES)
    op.execute(f"CREATE TYPE ceiling_category_new AS ENUM ({new_vals})")

    # ── 2. Detach column from old enum — cast to plain TEXT ──────────────────
    op.execute(
        "ALTER TABLE leads "
        "ALTER COLUMN category TYPE TEXT USING category::TEXT"
    )

    # ── 3. Remap old values → new values ─────────────────────────────────────
    op.execute("""
        UPDATE leads
        SET category = CASE category
            WHEN 'matviy_oq'      THEN 'odnotonny'
            WHEN 'yaltiroq_oq'    THEN 'odnotonny'
            WHEN 'qora_premium'   THEN 'qora_naqsh_uf'
            WHEN 'gulli_3d'       THEN 'gulli'
            WHEN 'mramor_dizayn'  THEN 'mramor'
            WHEN 'led_podsvetka'  THEN 'hi_tech'
            WHEN 'yulduzli_osmon' THEN 'kosmos'
            WHEN 'ikki_darajali'  THEN 'odnotonny'
            WHEN 'ofis_minimal'   THEN 'odnotonny'
            WHEN 'oshxona'        THEN 'oshxona'
            ELSE                       'odnotonny'
        END
    """)

    # ── 4. Cast TEXT column to the new enum ──────────────────────────────────
    op.execute(
        "ALTER TABLE leads "
        "ALTER COLUMN category TYPE ceiling_category_new "
        "USING category::ceiling_category_new"
    )

    # ── 5. Drop the old type ──────────────────────────────────────────────────
    op.execute("DROP TYPE ceiling_category")

    # ── 6. Rename new type to the canonical name ──────────────────────────────
    op.execute("ALTER TYPE ceiling_category_new RENAME TO ceiling_category")


def downgrade() -> None:
    # ── 1. Recreate old enum type ─────────────────────────────────────────────
    old_vals = ", ".join(f"'{v}'" for v in _OLD_VALUES)
    op.execute(f"CREATE TYPE ceiling_category_old AS ENUM ({old_vals})")

    # ── 2. Detach column from new enum — cast to TEXT ─────────────────────────
    op.execute(
        "ALTER TABLE leads "
        "ALTER COLUMN category TYPE TEXT USING category::TEXT"
    )

    # ── 3. Remap new values → old values ─────────────────────────────────────
    op.execute("""
        UPDATE leads
        SET category = CASE category
            WHEN 'gulli'         THEN 'gulli_3d'
            WHEN 'odnotonny'     THEN 'matviy_oq'
            WHEN 'mramor'        THEN 'mramor_dizayn'
            WHEN 'qora_naqsh_uf' THEN 'qora_premium'
            WHEN 'hi_tech'       THEN 'led_podsvetka'
            WHEN 'kosmos'        THEN 'yulduzli_osmon'
            WHEN 'osmon'         THEN 'yulduzli_osmon'
            WHEN 'oshxona'       THEN 'oshxona'
            WHEN 'naqsh_ramka'   THEN 'matviy_oq'
            WHEN 'naqsh_oq'      THEN 'matviy_oq'
            ELSE                      'matviy_oq'
        END
    """)

    # ── 4. Cast TEXT column back to old enum ──────────────────────────────────
    op.execute(
        "ALTER TABLE leads "
        "ALTER COLUMN category TYPE ceiling_category_old "
        "USING category::ceiling_category_old"
    )

    # ── 5. Drop the new type ──────────────────────────────────────────────────
    op.execute("DROP TYPE ceiling_category")

    # ── 6. Rename old type to the canonical name ──────────────────────────────
    op.execute("ALTER TYPE ceiling_category_old RENAME TO ceiling_category")
