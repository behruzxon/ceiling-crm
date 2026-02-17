"""
APScheduler entry point.
Runs as a separate process alongside the bot.
"""
from __future__ import annotations
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apps.scheduler.jobs.followup_jobs import register_followup_jobs
from apps.scheduler.jobs.broadcast_jobs import register_broadcast_jobs
from apps.scheduler.jobs.analytics_jobs import register_analytics_jobs
from apps.scheduler.jobs.cache_jobs import register_cache_jobs
from infrastructure.database.session import connect_database, disconnect_database
from infrastructure.cache.client import connect_redis, disconnect_redis
from shared.logging import configure_logging, get_logger

log = get_logger(__name__)


async def run_scheduler() -> None:
    configure_logging()
    await connect_database()
    await connect_redis()

    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    register_followup_jobs(scheduler)
    register_broadcast_jobs(scheduler)
    register_analytics_jobs(scheduler)
    register_cache_jobs(scheduler)

    scheduler.start()
    log.info("scheduler_started", job_count=len(scheduler.get_jobs()))

    try:
        await asyncio.Event().wait()  # run forever
    finally:
        scheduler.shutdown()
        await disconnect_database()
        await disconnect_redis()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
