"""
BroadcastService — audience segmentation and broadcast orchestration.
"""
from __future__ import annotations
from core.domain.broadcast import Broadcast, SegmentFilter
from core.repositories.broadcast_repo import AbstractBroadcastRepository
from shared.constants.enums import BroadcastStatus
from shared.logging import get_logger

log = get_logger(__name__)


class BroadcastService:
    """
    Manages broadcast creation, audience estimation, and execution.
    Delegates actual message sending to Celery tasks (rate-limited).
    """

    def __init__(self, broadcast_repo: AbstractBroadcastRepository) -> None:
        self._repo = broadcast_repo

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
        """
        Execute a broadcast: resolve audience, enqueue Celery tasks.
        TODO: implement batch send with rate limiting.
        """
        raise NotImplementedError
