"""Abstract tenant repository interface."""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from core.repositories.base import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database.models.tenant import TenantModel


class AbstractTenantRepository(BaseRepository["TenantModel", int]):
    """Contract for tenant persistence operations."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> TenantModel | None: ...

    @abstractmethod
    async def get_by_admin_user_id(self, admin_user_id: int) -> TenantModel | None: ...

    @abstractmethod
    async def slug_exists(self, slug: str) -> bool: ...

    @abstractmethod
    async def list_active_with_bot(self) -> list[TenantModel]: ...
