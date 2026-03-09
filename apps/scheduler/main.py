"""
APScheduler entry point.
Runs as a separate process alongside the bot.
"""
from __future__ import annotations
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apps.scheduler.jobs.billing_jobs import register_billing_jobs
from apps.scheduler.jobs.followup_jobs import register_followup_jobs
from apps.scheduler.jobs.broadcast_jobs import register_broadcast_jobs
from apps.scheduler.jobs.analytics_jobs import register_analytics_jobs
from apps.scheduler.jobs.bot_health_jobs import register_bot_health_jobs
from apps.scheduler.jobs.cache_jobs import register_cache_jobs
from infrastructure.database.session import connect_database, disconnect_database
from infrastructure.cache.client import connect_redis, disconnect_redis
from shared.logging import configure_logging, get_logger

log = get_logger(__name__)


async def run_scheduler() -> None:
    configure_logging()
    await connect_database()
    await connect_redis()

    scheduler = AsyncIOScheduler(
        timezone="Asia/Tashkent",
        job_defaults={
            "coalesce": True,         # collapse missed runs into one execution
            "max_instances": 1,       # never run the same job twice in parallel
            "misfire_grace_time": 60, # tolerate up to 60 s late start before skipping
        },
    )
    register_billing_jobs(scheduler)
    register_followup_jobs(scheduler)
    register_broadcast_jobs(scheduler)
    register_analytics_jobs(scheduler)
    register_cache_jobs(scheduler)
    register_bot_health_jobs(scheduler)

    scheduler.start()
    for job in scheduler.get_jobs():
        log.info(
            "scheduler_job_registered",
            job_id=job.id,
            trigger=str(job.trigger),
            next_run_time=str(job.next_run_time),
        )
    log.info("scheduler_started", job_count=len(scheduler.get_jobs()))

    try:
        await asyncio.Event().wait()  # run forever
    finally:
        scheduler.shutdown()
        await disconnect_database()
        await disconnect_redis()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
