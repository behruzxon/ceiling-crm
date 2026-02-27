"""Broadcast repository interface."""
from __future__ import annotations
from abc import abstractmethod
from datetime import datetime
from core.domain.broadcast import Broadcast, SegmentFilter
from core.repositories.base import BaseRepository
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType


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
        """Resolve legacy segment filter to list of matching user IDs."""
        ...

    @abstractmethod
    async def estimate_segment_size(self, segment: SegmentFilter) -> int: ...

    # ── v2 methods ────────────────────────────────────────────────────────

    @abstractmethod
    async def create_broadcast(
        self,
        segment_type: SegmentType,
        payload_type: PayloadType,
        text: str | None,
        file_id: str | None,
        created_by: int,
        lead_stage: str | None = None,
    ) -> int:
        """Create a PENDING broadcast record; return its new ID."""
        ...

    @abstractmethod
    async def mark_status(self, broadcast_id: int, status: BroadcastStatus) -> None:
        """Update the status column of a broadcast."""
        ...

    @abstractmethod
    async def inc_sent(self, broadcast_id: int, n: int = 1) -> None:
        """Atomically increment sent_count by n."""
        ...

    @abstractmethod
    async def inc_failed(self, broadcast_id: int, n: int = 1) -> None:
        """Atomically increment failed_count by n."""
        ...

    @abstractmethod
    async def finalize(self, broadcast_id: int, finished_at: datetime) -> None:
        """Set finished_at; caller should also call mark_status(DONE)."""
        ...

    @abstractmethod
    async def get_all_private_user_ids(self) -> list[int]:
        """Return IDs of all non-blocked users (ALL_PRIVATE segment)."""
        ...

    @abstractmethod
    async def get_user_ids_by_stage(self, lead_stage: str) -> list[int]:
        """Return user IDs whose current pipeline stage == lead_stage."""
        ...
