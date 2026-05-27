"""Abstract base repository interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
IDType = TypeVar("IDType", int, str)


class BaseRepository(ABC, Generic[T, IDType]):
    """
    Generic async repository interface.
    All concrete implementations live in infrastructure/database/repositories/.
    """

    @abstractmethod
    async def get_by_id(self, id: IDType) -> T | None: ...

    @abstractmethod
    async def create(self, entity: T) -> T: ...

    @abstractmethod
    async def update(self, entity: T) -> T: ...

    @abstractmethod
    async def delete(self, id: IDType) -> bool: ...
