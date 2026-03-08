"""PostgreSQL implementation of AbstractGroupSettingsRepository."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.group_settings import GroupSettings
from core.repositories.group_settings_repo import AbstractGroupSettingsRepository
from infrastructure.database.models.group_settings import GroupSettingsModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository

# Whitelist — only these fields may be toggled or set via set_field().
_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "welcome_enabled",
    "welcome_autodelete_seconds",
    "captcha_enabled",
    "link_block_enabled",
    "flood_enabled",
    "logs_enabled",
})


class PostgresGroupSettingsRepository(TenantScopedRepository, AbstractGroupSettingsRepository):
    """Concrete SQLAlchemy/PostgreSQL group settings repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    def _to_domain(self, model: GroupSettingsModel) -> GroupSettings:
        return GroupSettings(
            chat_id=model.chat_id,
            welcome_enabled=model.welcome_enabled,
            welcome_autodelete_seconds=model.welcome_autodelete_seconds,
            captcha_enabled=model.captcha_enabled,
            link_block_enabled=model.link_block_enabled,
            flood_enabled=model.flood_enabled,
            logs_enabled=model.logs_enabled,
            updated_at=model.updated_at,
        )

    async def get_by_id(self, id: int) -> GroupSettings | None:
        model = await self._session.get(GroupSettingsModel, id)
        if model is None:
            return None
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            return None
        return self._to_domain(model)

    async def get_or_create(self, chat_id: int) -> GroupSettings:
        """Insert with all defaults if missing; always returns current row."""
        values: dict = {"chat_id": chat_id}
        if self._tenant_id is not None:
            values["tenant_id"] = self._tenant_id
        await self._session.execute(
            pg_insert(GroupSettingsModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["chat_id"])
        )
        # Flush so the row is visible to the subsequent SELECT.
        await self._session.flush()
        model = await self._session.get(GroupSettingsModel, chat_id)
        assert model is not None  # guaranteed by insert-or-skip above
        return self._to_domain(model)

    async def set_field(self, chat_id: int, field: str, value: bool | int) -> GroupSettings:
        """Upsert a single settings field; returns the updated row."""
        if field not in _ALLOWED_FIELDS:
            raise ValueError(f"Unknown group settings field: {field!r}")

        insert_values: dict = {"chat_id": chat_id, field: value}
        if self._tenant_id is not None:
            insert_values["tenant_id"] = self._tenant_id
        stmt = (
            pg_insert(GroupSettingsModel)
            .values(**insert_values)
            .on_conflict_do_update(
                index_elements=["chat_id"],
                set_={
                    field: value,
                    "updated_at": sa.func.now(),
                },
            )
            .returning(GroupSettingsModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        return self._to_domain(model)

    # ── BaseRepository stubs (not used directly by service layer) ─────────

    async def create(self, entity: GroupSettings) -> GroupSettings:
        return await self.get_or_create(entity.chat_id)

    async def update(self, entity: GroupSettings) -> GroupSettings:
        model = await self._session.get(GroupSettingsModel, entity.chat_id)
        if model is None:
            raise ValueError(f"GroupSettings {entity.chat_id} not found")
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            raise ValueError(f"GroupSettings {entity.chat_id} not found")
        model.welcome_enabled = entity.welcome_enabled
        model.welcome_autodelete_seconds = entity.welcome_autodelete_seconds
        model.captcha_enabled = entity.captcha_enabled
        model.link_block_enabled = entity.link_block_enabled
        model.flood_enabled = entity.flood_enabled
        model.logs_enabled = entity.logs_enabled
        await self._session.flush()
        return self._to_domain(model)

    async def delete(self, id: int) -> bool:
        stmt = sa.delete(GroupSettingsModel).where(GroupSettingsModel.chat_id == id)
        if self._tenant_id is not None:
            stmt = stmt.where(GroupSettingsModel.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
