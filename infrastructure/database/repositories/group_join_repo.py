"""PostgreSQL implementation of AbstractGroupJoinRepository."""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.group_join_repo import AbstractGroupJoinRepository
from infrastructure.database.models.group_join_event import GroupJoinEventModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository


class PostgresGroupJoinRepository(TenantScopedRepository, AbstractGroupJoinRepository):
    """Concrete SQLAlchemy/PostgreSQL group join repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    async def upsert_join(
        self,
        group_id: int,
        user_id: int,
        joined_at: datetime | None = None,
    ) -> None:
        """INSERT … ON CONFLICT DO NOTHING — first join for (group, user) wins."""
        values: dict = {"group_id": group_id, "user_id": user_id}
        if joined_at is not None:
            values["joined_at"] = joined_at
        if self._tenant_id is not None:
            values["tenant_id"] = self._tenant_id
        stmt = (
            pg_insert(GroupJoinEventModel)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_group_join_events_group_user")
        )
        await self._session.execute(stmt)

    async def count_joins(
        self,
        group_id: int,
        since_dt: datetime,
        until_dt: datetime | None = None,
    ) -> int:
        """Count distinct users who joined *group_id* in [since_dt, until_dt)."""
        until_dt = until_dt or datetime.now(timezone.utc)
        stmt = (
            sa.select(sa.func.count())
            .select_from(GroupJoinEventModel)
            .where(
                GroupJoinEventModel.group_id == group_id,
                GroupJoinEventModel.joined_at >= since_dt,
                GroupJoinEventModel.joined_at < until_dt,
            )
        )
        stmt = self._apply_tenant_filter(stmt, GroupJoinEventModel)
        result = await self._session.execute(stmt)
        return result.scalar() or 0
