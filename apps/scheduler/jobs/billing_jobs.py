"""
apps.scheduler.jobs.billing_jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Daily billing expiration check.

Runs at 09:00 Asia/Tashkent:
1. Scans all trial/active tenants for upcoming or past expirations.
2. Sends 3-day and 1-day warnings to tenant admin_user_id.
3. Expires overdue tenants (sets billing_status='expired').
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from infrastructure.cache.distributed_lock import scheduler_lock
from shared.logging import get_logger

log = get_logger(__name__)


def register_billing_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the daily billing expiration check job."""
    scheduler.add_job(
        check_billing_expirations,
        trigger="cron",
        hour=9,
        minute=0,
        id="billing_expiration_check",
        replace_existing=True,
    )


@scheduler_lock("billing_expiration_check")
async def check_billing_expirations() -> None:
    """Scan all tenants for upcoming or past billing expirations."""
    from core.services.billing_service import BillingService
    from infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        svc = BillingService(session)
        result = await svc.process_expirations()
        await session.commit()

    if result["warnings_sent"] or result["expired"]:
        log.info("billing_expiration_check_done", **result)
