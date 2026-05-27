"""cleanup invalid user ids (id <= 0) and add CHECK constraint

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-02-27 19:00:00.000000

Background
----------
AuthMiddleware previously upserted every Telegram ``event_from_user`` into
the ``users`` table without validating the id.  This allowed non-positive
ids to be stored:

  * Negative ids — Telegram groups / supergroups / channels
    (e.g. -8458020670, -1617969070, -8075614465)
  * ``is_bot=True`` entities — GroupAnonymousBot (id 1087968824, a positive
    value but not a real CRM user) and other service bots

The broadcast worker's ``get_all_private_user_ids()`` then included those
rows in the target list, causing:

    Bad Request: chat not found

when the Telegram API was asked to send a message to a group/channel id.

Fix
---
1. Soft-delete existing invalid rows: set ``is_blocked = true`` so they are
   excluded from all active queries but historical data is preserved.
   (A hard-delete variant is provided in the comments below.)

2. Add a CHECK constraint ``users_id_positive`` enforcing ``id > 0`` at the
   database level.  This is the last line of defence — it will raise a
   ``CheckViolationError`` even if application-layer guards are bypassed.

Application changes (no schema migration required)
--------------------------------------------------
* ``AuthMiddleware``: skips upsert when ``tg_user.id <= 0`` or
  ``tg_user.is_bot is True``.
* ``PostgresUserRepository.upsert()``: raises ``ValueError`` for id <= 0.
* ``PostgresBroadcastRepository.get_all_private_user_ids()``: adds
  ``UserModel.id > 0`` filter as a belt-and-suspenders query guard.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Step 1: soft-delete all rows with non-positive id ────────────────────
    # We mark them blocked rather than deleting so the data can be audited.
    # To hard-delete instead, replace the UPDATE with:
    #   op.execute("DELETE FROM users WHERE id <= 0")
    op.execute(
        sa.text(
            "UPDATE users SET is_blocked = true, updated_at = now() WHERE id <= 0"
        )
    )

    # ── Step 2: add CHECK constraint so future invalid inserts are rejected ──
    op.create_check_constraint(
        "users_id_positive",
        "users",
        "id > 0",
    )


def downgrade() -> None:
    op.drop_constraint("users_id_positive", "users", type_="check")
    # The soft-deleted rows are NOT restored on downgrade — they remain blocked.
    # If you need to undo the data change, run manually:
    #   UPDATE users SET is_blocked = false WHERE id <= 0;
