"""
APScheduler entry point.
Runs as a separate process alongside the bot.
"""
from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.scheduler.jobs.admin_escalation_jobs import register_admin_escalation_jobs
from apps.scheduler.jobs.agent_execution_jobs import register_agent_execution_jobs
from apps.scheduler.jobs.agent_followup_jobs import register_agent_followup_jobs
from apps.scheduler.jobs.analytics_jobs import register_analytics_jobs
from apps.scheduler.jobs.approved_execution_sender_jobs import (
    register_approved_execution_sender_jobs,
)
from apps.scheduler.jobs.auto_sales_jobs import register_auto_sales_jobs
from apps.scheduler.jobs.broadcast_jobs import register_broadcast_jobs
from apps.scheduler.jobs.cache_jobs import register_cache_jobs
from apps.scheduler.jobs.closing_jobs import register_closing_jobs
from apps.scheduler.jobs.conversation_intelligence_jobs import (
    register_conversation_intelligence_jobs,
)
from apps.scheduler.jobs.crm_daily_report_jobs import register_crm_daily_report_jobs
from apps.scheduler.jobs.followup_jobs import register_followup_jobs
from apps.scheduler.jobs.outcome_resolver_jobs import register_outcome_resolver_jobs
from apps.scheduler.jobs.sales_autopilot_jobs import register_sales_autopilot_jobs
from infrastructure.cache.client import connect_redis, disconnect_redis
from infrastructure.database.session import connect_database, disconnect_database
from shared.logging import configure_logging, get_logger

log = get_logger(__name__)


def _add_error_listener(scheduler: AsyncIOScheduler) -> None:
    """Log scheduler job errors to system_errors table."""
    from apscheduler.events import EVENT_JOB_ERROR

    def _on_job_error(event: object) -> None:
        exc = getattr(event, "exception", None)
        job_id = getattr(event, "job_id", "unknown")
        if exc:
            log.exception("scheduler_job_error", job_id=job_id)
            try:
                from infrastructure.error_logger import log_system_error
                asyncio.ensure_future(
                    log_system_error("scheduler", exc, message=f"job={job_id}: {exc}")
                )
            except Exception:
                pass

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)


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
    _add_error_listener(scheduler)
    register_followup_jobs(scheduler)
    register_agent_followup_jobs(scheduler)
    register_admin_escalation_jobs(scheduler)
    register_broadcast_jobs(scheduler)
    register_analytics_jobs(scheduler)
    register_cache_jobs(scheduler)
    register_conversation_intelligence_jobs(scheduler)
    register_sales_autopilot_jobs(scheduler)
    register_closing_jobs(scheduler)
    register_auto_sales_jobs(scheduler)
    register_outcome_resolver_jobs(scheduler)
    register_agent_execution_jobs(scheduler)
    register_approved_execution_sender_jobs(scheduler)
    register_crm_daily_report_jobs(scheduler)

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
