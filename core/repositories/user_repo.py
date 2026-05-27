"""User repository interface."""

from __future__ import annotations

from abc import abstractmethod

from core.domain.user import User
from core.repositories.base import BaseRepository
from shared.constants.enums import UserRole


class AbstractUserRepository(BaseRepository[User, int]):
    """Contract for user persistence operations."""

    @abstractmethod
    async def get_by_id(self, id: int) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def upsert(self, user: User) -> User:
        """Insert or update user by Telegram user_id."""
        ...

    @abstractmethod
    async def get_by_role(self, role: UserRole) -> list[User]: ...

    @abstractmethod
    async def count_active(self) -> int: ...
