"""Scheduler job — daily operator digest computation.

Safety:
  * Disabled by default (``CRM_OPERATOR_DIGEST_ENABLED=false``).
  * Delivery is disabled by default (``CRM_OPERATOR_DIGEST_DELIVERY_ENABLED=false``);
    even when the digest job runs it only builds + logs the digest, never
    sends anything externally.
  * No Telegram, no OpenAI, no destructive DB operations.
  * Errors swallowed and logged; never crashes the scheduler.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)

JOB_ID = "crm_operator_digest_daily"


def register_operator_digest_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the daily digest job.

    Always registered so the flag can be flipped without a restart. The
    schedule runs once per day at the configured hour (default 09:00).
    """
    try:
        from shared.config import get_settings

        hour = int(getattr(get_settings().business, "crm_operator_digest_hour", 9) or 9)
    except Exception:
        hour = 9

    scheduler.add_job(
        run_operator_digest_job,
        trigger="cron",
        hour=hour,
        minute=0,
        id=JOB_ID,
        replace_existing=True,
    )


async def run_operator_digest_job() -> None:
    """Build the digest, log a summary, optionally deliver (default OFF).

    Behavior:
      * If ``CRM_OPERATOR_DIGEST_ENABLED`` is false → no-op.
      * Build digest from DB rows; log severity + key counters.
      * Delivery branch only runs if ``CRM_OPERATOR_DIGEST_DELIVERY_ENABLED``
        is also true — currently a defensive no-op (no aiogram import here).
    """
    try:
        from shared.config import get_settings

        settings = get_settings()
        if not getattr(settings.business, "crm_operator_digest_enabled", False):
            log.debug("operator_digest_disabled")
            return
    except Exception:
        log.exception("operator_digest_config_error")
        return

    try:
        import sqlalchemy as sa

        from core.services.crm_operator_digest_service import build_digest
        from infrastructure.database.models.crm_operator_handoff import (
            CRMOperatorHandoffModel,
        )
        from infrastructure.database.session import get_session_factory

        factory = get_session_factory()
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=24)

        async with factory() as session:
            q = sa.select(CRMOperatorHandoffModel).where(
                sa.or_(
                    CRMOperatorHandoffModel.status.in_(
                        ("open", "waiting_phone", "assigned", "contacted")
                    ),
                    sa.and_(
                        CRMOperatorHandoffModel.status.in_(("resolved", "cancelled", "expired")),
                        CRMOperatorHandoffModel.updated_at >= cutoff,
                    ),
                )
            )
            result = await session.execute(q)
            handoffs = list(result.scalars().all())

        digest = build_digest(now=now, handoffs=handoffs, missed_leads=[])
        log.info(
            "operator_digest_built",
            severity=digest.summary.severity,
            total_open=digest.summary.total_open,
            urgent_open=digest.summary.urgent_open,
            high_open=digest.summary.high_open,
            expired_today=digest.summary.expired_today,
            oldest_wait_minutes=digest.summary.oldest_wait_minutes,
        )

        if getattr(settings.business, "crm_operator_digest_delivery_enabled", False):
            # Delivery is intentionally a no-op until an internal-only,
            # admin-DM channel is wired in a later step. We log only.
            log.info("operator_digest_delivery_skipped_no_channel")
        else:
            log.debug("operator_digest_delivery_disabled")
    except Exception:
        log.exception("operator_digest_job_error")
