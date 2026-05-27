"""PostgreSQL implementation of AbstractAdminGroupRepository."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.admin_group_repo import AbstractAdminGroupRepository
from infrastructure.database.models.admin_group import AdminGroupModel


class PostgresAdminGroupRepository(AbstractAdminGroupRepository):
    """Concrete SQLAlchemy/PostgreSQL admin group repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, chat_id: int, title: str) -> None:
        """INSERT … ON CONFLICT DO UPDATE — inserts or refreshes title."""
        stmt = (
            pg_insert(AdminGroupModel)
            .values(chat_id=chat_id, title=title)
            .on_conflict_do_update(
                index_elements=["chat_id"],
                set_={"title": title},
            )
        )
        await self._session.execute(stmt)

    async def list_all_chat_ids(self) -> list[int]:
        """Return all tracked admin-group chat IDs."""
        stmt = sa.select(AdminGroupModel.chat_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def remove(self, chat_id: int) -> None:
        """DELETE FROM admin_groups WHERE chat_id = :chat_id (no-op if missing)."""
        stmt = sa.delete(AdminGroupModel).where(AdminGroupModel.chat_id == chat_id)
        await self._session.execute(stmt)
