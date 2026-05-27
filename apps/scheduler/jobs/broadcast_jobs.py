"""Scheduled broadcast execution jobs."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_broadcast_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register broadcast queue processor."""
    scheduler.add_job(
        process_scheduled_broadcasts,
        trigger="interval",
        minutes=1,
        id="process_broadcasts",
        replace_existing=True,
    )


async def process_scheduled_broadcasts() -> None:
    """Find due broadcasts and enqueue Celery tasks.

    TODO: query broadcasts WHERE status='pending' AND scheduled_at <= now()
          and dispatch process_broadcast_batch.delay(broadcast_id) per row.
    """
    log.debug("broadcast_scheduler_not_implemented")
