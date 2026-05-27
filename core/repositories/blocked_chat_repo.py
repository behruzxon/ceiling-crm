"""Abstract repository interface for blocked_chats."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractBlockedChatRepository(ABC):
    """Contract for blocked_chats persistence.

    A "blocked chat" is any private user or group whose Telegram chat_id has
    been confirmed as permanently unreachable (bot blocked, kicked, chat
    deleted, etc.).  The repository provides:

    - bulk_filter_blocked: remove known-blocked IDs from a candidate list
      with a single query (no N+1).
    - upsert_block: idempotent write — creates a new row or increments the
      seen_count / refreshes last_seen_at on conflict.
    """

    @abstractmethod
    async def bulk_filter_blocked(self, chat_ids: list[int]) -> list[int]:
        """Return *chat_ids* with all known-blocked IDs removed.

        Executes a single ``WHERE chat_id IN (…)`` query.
        Returns the input list unchanged when *chat_ids* is empty.
        Order is preserved.
        """
        ...

    @abstractmethod
    async def upsert_block(self, chat_id: int, reason: str) -> bool:
        """Persist a blocked chat.

        - If *chat_id* is not yet in the table: INSERT, return ``True``.
        - If *chat_id* already exists: UPDATE reason / last_seen_at /
          seen_count, return ``False``.

        *reason* should be one of ``"blocked"`` | ``"forbidden"`` | ``"other"``.
        """
        ...
