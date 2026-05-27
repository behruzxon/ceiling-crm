"""Abstract repository interface for admin groups."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractAdminGroupRepository(ABC):
    """Contract for admin_groups persistence.

    Tracks groups where the bot has admin privileges.
    Used to resolve the ADMIN_GROUPS broadcast segment.
    """

    @abstractmethod
    async def upsert(self, chat_id: int, title: str) -> None:
        """Insert the group if missing; update title if it has changed."""
        ...

    @abstractmethod
    async def list_all_chat_ids(self) -> list[int]:
        """Return all tracked admin-group chat IDs."""
        ...

    @abstractmethod
    async def remove(self, chat_id: int) -> None:
        """Remove a group from admin_groups (no-op if not present)."""
        ...
