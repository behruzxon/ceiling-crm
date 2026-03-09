"""
apps.scheduler.jobs.bot_health_jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Periodic health check for all active tenant bots.

Runs every 5 minutes:
1. Iterates all RUNNING bots in BotRegistry.
2. Calls ``getMe()`` on each.
3. Updates ``last_health_check`` in DB and registry state.
4. Logs warnings for failed bots.

No-op when registry has 0 bots (harmless in single-bot mode).
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_bot_health_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the periodic bot health check job."""
    scheduler.add_job(
        check_bot_health,
        trigger="interval",
        minutes=5,
        id="bot_health_check",
        replace_existing=True,
    )


async def check_bot_health() -> None:
    """Health-check all running tenant bots."""
    from datetime import datetime, timezone

    from core.services.bot_registry import BotStatus, get_bot_registry
    from infrastructure.database.models.tenant import TenantModel
    from infrastructure.database.session import get_session_factory

    registry = get_bot_registry()
    if registry.bot_count == 0:
        return

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    healthy = 0
    failed = 0

    for bot in registry.all_bots():
        tenant_id = registry.get_tenant_id(bot.id)
        if tenant_id is None:
            continue

        state = registry.get_bot_state(tenant_id)
        if state is None or state.status != BotStatus.RUNNING:
            continue

        try:
            await bot.get_me()
            state.last_health_check = now

            async with factory() as session:
                tenant = await session.get(TenantModel, tenant_id)
                if tenant:
                    tenant.last_health_check = now
                    await session.commit()
            healthy += 1
        except Exception:
            state.last_error = "health_check_failed"
            state.last_error_at = now
            state.error_count += 1
            failed += 1
            log.warning(
                "bot_health_check_failed",
                tenant_id=tenant_id,
                bot_id=bot.id,
                error_count=state.error_count,
            )

    if healthy + failed > 0:
        log.info("bot_health_check_done", healthy=healthy, failed=failed)
