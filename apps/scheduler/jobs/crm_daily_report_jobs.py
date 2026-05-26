"""Scheduler job for daily CRM report generation."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shared.logging import get_logger

log = get_logger(__name__)


def register_crm_daily_report_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        generate_daily_crm_report_job,
        "cron", hour=20, minute=0, id="crm_daily_report",
    )


async def generate_daily_crm_report_job() -> None:
    try:
        from shared.config import get_settings
        if not get_settings().business.crm_daily_report_enabled:
            return
        log.info("crm_daily_report_generating")
    except Exception:
        log.warning("crm_daily_report_job_error")
