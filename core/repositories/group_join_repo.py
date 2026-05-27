"""Abstract repository interface for group join events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class AbstractGroupJoinRepository(ABC):
    """Contract for group_join_events persistence.

    Records the first time each user joins a tracked Telegram group.
    Used by StatsService to count group joins per period.
    """

    @abstractmethod
    async def upsert_join(
        self,
        group_id: int,
        user_id: int,
        joined_at: datetime | None = None,
    ) -> None:
        """Record a join event.  INSERT … ON CONFLICT DO NOTHING (first join wins)."""
        ...

    @abstractmethod
    async def count_joins(
        self,
        group_id: int,
        since_dt: datetime,
        until_dt: datetime | None = None,
    ) -> int:
        """Count users who joined *group_id* in [since_dt, until_dt).

        *until_dt* defaults to now() when not provided.
        """
        ...
