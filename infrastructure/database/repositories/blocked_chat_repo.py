"""PostgreSQL implementation of AbstractBlockedChatRepository."""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.blocked_chat_repo import AbstractBlockedChatRepository
from infrastructure.database.models.blocked_chat import BlockedChatModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository


class PostgresBlockedChatRepository(TenantScopedRepository, AbstractBlockedChatRepository):
    """Concrete SQLAlchemy / PostgreSQL blocked-chat repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    # ── Read ─────────────────────────────────────────────────────────────────

    async def bulk_filter_blocked(self, chat_ids: list[int]) -> list[int]:
        """Return *chat_ids* minus any IDs already in blocked_chats.

        Single ``SELECT chat_id FROM blocked_chats WHERE chat_id IN (…)``.
        Order of the returned list matches the input order.
        """
        if not chat_ids:
            return []

        stmt = sa.select(BlockedChatModel.chat_id).where(
            BlockedChatModel.chat_id.in_(chat_ids)
        )
        stmt = self._apply_tenant_filter(stmt, BlockedChatModel)
        result = await self._session.execute(stmt)
        blocked: frozenset[int] = frozenset(result.scalars().all())
        return [cid for cid in chat_ids if cid not in blocked]

    # ── Write ─────────────────────────────────────────────────────────────────

    async def upsert_block(self, chat_id: int, reason: str) -> bool:
        """Upsert a blocked chat entry.

        Uses PostgreSQL ``ON CONFLICT DO UPDATE`` and reads back the
        ``xmax`` system column to determine whether the row was freshly
        inserted (``xmax = 0``) or updated (``xmax != 0``).

        Returns ``True`` if this is a brand-new entry, ``False`` if it
        already existed and was refreshed.
        """
        now = datetime.now(timezone.utc)

        values: dict = {
            "chat_id": chat_id,
            "reason": reason,
            "first_seen_at": now,
            "last_seen_at": now,
            "seen_count": 1,
        }
        if self._tenant_id is not None:
            values["tenant_id"] = self._tenant_id

        insert_stmt = pg_insert(BlockedChatModel).values(**values)

        on_conflict_kwargs: dict = {
            "index_elements": ["chat_id"],
            "set_": {
                "reason": insert_stmt.excluded.reason,
                "last_seen_at": insert_stmt.excluded.last_seen_at,
                # Increment the existing counter by 1; do NOT reset it.
                "seen_count": BlockedChatModel.seen_count + 1,
            },
        }
        # Only update rows belonging to the same tenant (prevent cross-tenant
        # data overwrite when multiple tenants encounter the same blocked chat).
        if self._tenant_id is not None:
            on_conflict_kwargs["where"] = (
                BlockedChatModel.tenant_id == self._tenant_id
            )

        upsert_stmt = insert_stmt.on_conflict_do_update(
            **on_conflict_kwargs,
        ).returning(
            # xmax = 0  →  fresh INSERT (transaction ID is 0 = never updated)
            # xmax != 0 →  row existed and was UPDATE'd
            sa.literal_column("(xmax = 0)").label("is_new")
        )

        result = await self._session.execute(upsert_stmt)
        row = result.fetchone()
        return bool(row.is_new) if row else True
