"""Scheduled broadcast execution jobs."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler


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
    """Find due broadcasts and enqueue Celery tasks. TODO: implement."""
    raise NotImplementedError
