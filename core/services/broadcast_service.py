"""
BroadcastService — audience segmentation and broadcast orchestration.
"""

from __future__ import annotations

from datetime import datetime

from core.domain.broadcast import Broadcast, SegmentFilter
from core.repositories.broadcast_repo import AbstractBroadcastRepository
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType
from shared.logging import get_logger

log = get_logger(__name__)


class BroadcastService:
    """
    Manages broadcast creation, audience estimation, and execution.
    Delegates actual message sending to Celery tasks (rate-limited).
    """

    def __init__(self, broadcast_repo: AbstractBroadcastRepository) -> None:
        self._repo = broadcast_repo

    # ── legacy v1 stubs ───────────────────────────────────────────────────

    async def create_broadcast(
        self,
        title: str,
        message_template: str,
        segment: SegmentFilter,
        created_by: int,
        scheduled_at: object = None,
        media_file_id: str | None = None,
        media_type: str | None = None,
    ) -> Broadcast:
        """Create a new broadcast in DRAFT status. TODO: implement."""
        raise NotImplementedError

    async def estimate_reach(self, segment: SegmentFilter) -> int:
        """Return estimated recipient count for a segment. TODO: implement."""
        raise NotImplementedError

    async def schedule_broadcast(self, broadcast_id: int, actor_id: int) -> Broadcast:
        """Move broadcast from DRAFT to SCHEDULED. TODO: implement."""
        raise NotImplementedError

    async def execute_broadcast(self, broadcast_id: int) -> None:
        """Execute a broadcast: resolve audience, enqueue Celery tasks."""
        raise NotImplementedError

    # ── v2 methods ────────────────────────────────────────────────────────

    async def create_broadcast_v2(
        self,
        segment_type: SegmentType,
        payload_type: PayloadType,
        text: str | None,
        file_id: str | None,
        created_by: int,
        lead_stage: str | None = None,
    ) -> int:
        """Create a PENDING broadcast record and return its ID."""
        broadcast_id = await self._repo.create_broadcast(
            segment_type=segment_type,
            payload_type=payload_type,
            text=text,
            file_id=file_id,
            created_by=created_by,
            lead_stage=lead_stage,
        )
        log.info(
            "broadcast_created",
            broadcast_id=broadcast_id,
            segment_type=segment_type.value,
            payload_type=payload_type.value,
        )
        return broadcast_id

    async def mark_status(self, broadcast_id: int, status: BroadcastStatus) -> None:
        """Update the status of a broadcast."""
        await self._repo.mark_status(broadcast_id, status)

    async def inc_sent(self, broadcast_id: int, n: int = 1) -> None:
        """Atomically increment the sent counter."""
        await self._repo.inc_sent(broadcast_id, n)

    async def inc_failed(self, broadcast_id: int, n: int = 1) -> None:
        """Atomically increment the failed counter."""
        await self._repo.inc_failed(broadcast_id, n)

    async def finalize(self, broadcast_id: int, finished_at: datetime) -> None:
        """Record the finish timestamp."""
        await self._repo.finalize(broadcast_id, finished_at)

    async def get_broadcast(self, broadcast_id: int) -> Broadcast | None:
        """Load a broadcast record by ID."""
        return await self._repo.get_by_id(broadcast_id)

    async def estimate_reach_v2(
        self,
        segment_type: SegmentType,
        lead_stage: str | None = None,
    ) -> int:
        """Estimate the number of targets for a v2 segment."""
        if segment_type == SegmentType.LEAD_STAGE and lead_stage:
            ids = await self._repo.get_user_ids_by_stage(lead_stage)
        else:
            ids = await self._repo.get_all_private_user_ids()
        return len(ids)

    async def get_all_private_user_ids(self) -> list[int]:
        return await self._repo.get_all_private_user_ids()

    async def get_user_ids_by_stage(self, lead_stage: str) -> list[int]:
        return await self._repo.get_user_ids_by_stage(lead_stage)
