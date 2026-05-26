"""Scheduler jobs for agent execution queue maintenance."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_agent_execution_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        expire_pending_executions,
        "interval", minutes=5, id="agent_expire_pending_executions",
    )


async def expire_pending_executions() -> None:
    """Expire proposed/approved execution records past their TTL."""
    try:
        from shared.config import get_settings
        if not get_settings().business.agent_execution_queue_enabled:
            return

        from infrastructure.database.session import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_execution_queue_service import (
                AgentExecutionQueueService,
            )
            svc = AgentExecutionQueueService(session)
            count = await svc.expire_pending()
            await session.commit()

        if count > 0:
            log.info("agent_executions_expired", count=count)
    except Exception:
        log.warning("agent_execution_expire_job_error")
