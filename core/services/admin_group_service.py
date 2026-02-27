"""Business logic for tracked admin groups."""
from __future__ import annotations

from core.repositories.admin_group_repo import AbstractAdminGroupRepository
from shared.logging import get_logger

log = get_logger(__name__)


class AdminGroupService:
    """Thin service wrapper over AbstractAdminGroupRepository."""

    def __init__(self, repo: AbstractAdminGroupRepository) -> None:
        self._repo = repo

    async def upsert_admin_group(self, chat_id: int, title: str) -> None:
        """Record (or refresh the title of) a group where the bot is admin."""
        await self._repo.upsert(chat_id, title)
        log.info("admin_group_upserted", chat_id=chat_id, title=title)

    async def list_all_chat_ids(self) -> list[int]:
        """Return all admin-group chat IDs for broadcast delivery."""
        return await self._repo.list_all_chat_ids()
