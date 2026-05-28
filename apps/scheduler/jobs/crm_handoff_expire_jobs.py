"""Scheduler job — auto-expire stale handoff requests.

Safety:
  * Disabled by default (``CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED=false``).
  * No external sends — only DB status update to ``expired``.
  * No destructive deletes.
  * Errors are caught and logged; never crash the scheduler.
"""

from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)

JOB_ID = "crm_handoff_auto_expire"
DEFAULT_INTERVAL_MINUTES = 15


def register_handoff_expire_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the handoff auto-expire interval job.

    The job is always registered so it can be flipped on by toggling the
    config flag without restarting the scheduler. When the flag is off the
    job is a safe no-op.
    """
    scheduler.add_job(
        run_handoff_expire_job,
        trigger="interval",
        minutes=DEFAULT_INTERVAL_MINUTES,
        id=JOB_ID,
        replace_existing=True,
    )


async def run_handoff_expire_job() -> None:
    """Expire stale open/waiting_phone/assigned handoffs.

    Behavior:
      * If feature flag is off → no-op (returns silently).
      * If on → opens a session, calls service, logs summary.
      * Never raises; all errors are swallowed and logged.
    """
    try:
        from shared.config import get_settings

        settings = get_settings()
        business = settings.business

        if not getattr(business, "crm_operator_handoff_auto_expire_enabled", False):
            log.debug("handoff_auto_expire_disabled")
            return

        expire_hours = int(getattr(business, "crm_operator_handoff_expire_hours", 24) or 24)
        batch_limit = int(getattr(business, "crm_operator_handoff_expire_batch_limit", 100) or 100)
    except Exception:
        log.exception("handoff_auto_expire_config_error")
        return

    try:
        from core.services.crm_operator_handoff_service import CRMOperatorHandoffService
        from infrastructure.database.session import get_session_factory

        factory = get_session_factory()
        now = datetime.now(UTC)
        async with factory() as session:
            service = CRMOperatorHandoffService(session=session)
            result = await service.expire_stale_handoffs(
                now=now,
                expire_hours=expire_hours,
                limit=batch_limit,
            )

        log.info(
            "handoff_auto_expire_done",
            scanned=result.scanned,
            expired_count=result.expired_count,
            skipped_count=result.skipped_count,
            error_count=len(result.errors),
        )
    except Exception:
        log.exception("handoff_auto_expire_job_error")
