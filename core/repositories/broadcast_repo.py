"""Broadcast repository interface."""
from __future__ import annotations
from abc import abstractmethod
from datetime import datetime
from core.domain.broadcast import Broadcast, SegmentFilter
from core.repositories.base import BaseRepository
from shared.constants.enums import BroadcastStatus


class AbstractBroadcastRepository(BaseRepository[Broadcast, int]):
    """Contract for broadcast persistence."""

    @abstractmethod
    async def get_due_broadcasts(self, as_of: datetime) -> list[Broadcast]:
        """Return scheduled broadcasts whose scheduled_at <= as_of."""
        ...

    @abstractmethod
    async def update_counts(
        self, broadcast_id: int, sent_delta: int, failed_delta: int
    ) -> None: ...

    @abstractmethod
    async def get_segment_user_ids(self, segment: SegmentFilter) -> list[int]:
        """Resolve segment filter to list of matching user IDs."""
        ...

    @abstractmethod
    async def estimate_segment_size(self, segment: SegmentFilter) -> int: ...
