"""PostgreSQL implementation of AbstractTenantRepository."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.tenant_repo import AbstractTenantRepository
from infrastructure.database.models.tenant import TenantModel


class PostgresTenantRepository(AbstractTenantRepository):
    """Concrete SQLAlchemy/PostgreSQL tenant repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: int) -> TenantModel | None:
        return await self._session.get(TenantModel, id)

    async def get_by_slug(self, slug: str) -> TenantModel | None:
        result = await self._session.execute(
            select(TenantModel).where(TenantModel.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_admin_user_id(self, admin_user_id: int) -> TenantModel | None:
        result = await self._session.execute(
            select(TenantModel).where(TenantModel.admin_user_id == admin_user_id)
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        result = await self._session.execute(
            select(TenantModel.id).where(TenantModel.slug == slug).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def create(self, entity: TenantModel) -> TenantModel:
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: TenantModel) -> TenantModel:
        merged = await self._session.merge(entity)
        await self._session.flush()
        return merged

    async def list_active_with_bot(self) -> list[TenantModel]:
        result = await self._session.execute(
            select(TenantModel).where(
                TenantModel.is_active == True,  # noqa: E712
                TenantModel.bot_token.isnot(None),
            )
        )
        return list(result.scalars().all())

    async def delete(self, id: int) -> bool:
        tenant = await self.get_by_id(id)
        if tenant:
            await self._session.delete(tenant)
            return True
        return False
