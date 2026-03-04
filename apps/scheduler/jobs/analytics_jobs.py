"""Daily analytics aggregation jobs."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shared.logging import get_logger

log = get_logger(__name__)


def register_analytics_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        aggregate_daily_stats,
        trigger="cron",
        hour=23, minute=59,
        id="analytics_daily",
        replace_existing=True,
    )


async def aggregate_daily_stats() -> None:
    """Aggregate daily business metrics. TODO: implement via AnalyticsService."""
    log.debug("analytics_daily_not_implemented")
