"""PostgreSQL implementation of AbstractAdminGroupRepository."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.admin_group_repo import AbstractAdminGroupRepository
from infrastructure.database.models.admin_group import AdminGroupModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository


class PostgresAdminGroupRepository(TenantScopedRepository, AbstractAdminGroupRepository):
    """Concrete SQLAlchemy/PostgreSQL admin group repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    async def upsert(self, chat_id: int, title: str) -> None:
        """INSERT … ON CONFLICT DO UPDATE — inserts or refreshes title."""
        values: dict = {"chat_id": chat_id, "title": title}
        if self._tenant_id is not None:
            values["tenant_id"] = self._tenant_id

        on_conflict_kwargs: dict = {
            "index_elements": ["chat_id"],
            "set_": {"title": title},
        }
        # Only update rows belonging to the same tenant (prevent cross-tenant
        # data overwrite when multiple tenants share the same admin group).
        if self._tenant_id is not None:
            on_conflict_kwargs["where"] = (
                AdminGroupModel.tenant_id == self._tenant_id
            )

        stmt = pg_insert(AdminGroupModel).values(**values).on_conflict_do_update(
            **on_conflict_kwargs,
        )
        await self._session.execute(stmt)

    async def list_all_chat_ids(self) -> list[int]:
        """Return all tracked admin-group chat IDs."""
        stmt = sa.select(AdminGroupModel.chat_id)
        stmt = self._apply_tenant_filter(stmt, AdminGroupModel)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def remove(self, chat_id: int) -> None:
        """DELETE FROM admin_groups WHERE chat_id = :chat_id (no-op if missing)."""
        stmt = sa.delete(AdminGroupModel).where(AdminGroupModel.chat_id == chat_id)
        if self._tenant_id is not None:
            stmt = stmt.where(AdminGroupModel.tenant_id == self._tenant_id)
        await self._session.execute(stmt)
