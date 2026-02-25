"""Abstract repository interface for warranty records."""
from __future__ import annotations

from abc import abstractmethod

from core.domain.warranty import Warranty
from core.repositories.base import BaseRepository


class AbstractWarrantyRepository(BaseRepository[Warranty, int]):

    @abstractmethod
    async def get_by_id(self, id: int) -> Warranty | None: ...

    @abstractmethod
    async def get_by_lead(self, lead_id: int) -> Warranty | None:
        """Return the warranty for *lead_id*, or None if not yet issued."""
        ...

    @abstractmethod
    async def create(self, entity: Warranty) -> Warranty: ...

    @abstractmethod
    async def update(self, entity: Warranty) -> Warranty: ...

    @abstractmethod
    async def delete(self, id: int) -> bool: ...
