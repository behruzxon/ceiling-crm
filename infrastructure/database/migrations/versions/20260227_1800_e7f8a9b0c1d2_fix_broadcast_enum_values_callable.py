"""fix broadcast ORM enum serialization (values_callable)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-02-27 18:00:00.000000

Root cause
----------
BroadcastModel columns segment_type, payload_type, and status used
``sa.Enum(PythonEnum, name="...")`` without ``values_callable``.

Without values_callable, SQLAlchemy serialises Python enum **names**
(e.g. "ALL_PRIVATE") instead of **values** (e.g. "all_private") when
binding INSERT/UPDATE parameters.  The DB enum types were created with
lowercase values by the d6e7f8a9b0c1 migration, so every INSERT raised:

    InvalidTextRepresentationError: invalid input value for enum
    segment_type: "ALL_PRIVATE"

Fix
---
Added ``values_callable=lambda x: [e.value for e in x]`` to all three
enum columns in infrastructure/database/models/broadcast.py, matching
the pattern already used by UserModel.role.

No schema change is required — the DB types already contain the correct
lowercase values.  This migration is a no-op; it exists solely to:
  1. Record the fix at the correct position in the revision chain.
  2. Allow ``alembic upgrade head`` to succeed without errors.
"""
from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema changes needed — DB enum values were already correct.
    # The fix is purely in the ORM model (values_callable).
    pass


def downgrade() -> None:
    pass
