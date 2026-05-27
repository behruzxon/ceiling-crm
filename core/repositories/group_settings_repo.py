"""Abstract repository interface for group settings."""

from __future__ import annotations

from abc import abstractmethod

from core.domain.group_settings import GroupSettings
from core.repositories.base import BaseRepository


class AbstractGroupSettingsRepository(BaseRepository[GroupSettings, int]):

    @abstractmethod
    async def get_by_id(self, id: int) -> GroupSettings | None: ...

    @abstractmethod
    async def get_or_create(self, chat_id: int) -> GroupSettings:
        """Return existing settings row or insert one with all defaults."""
        ...

    @abstractmethod
    async def set_field(self, chat_id: int, field: str, value: bool | int) -> GroupSettings:
        """Upsert a single field; raises ValueError for unknown field names."""
        ...
