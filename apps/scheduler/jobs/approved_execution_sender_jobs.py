"""Scheduler job for sending approved agent execution payloads."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_approved_execution_sender_jobs(
    scheduler: AsyncIOScheduler,
) -> None:
    scheduler.add_job(
        process_approved_executions,
        "interval", minutes=1, id="agent_process_approved_executions",
    )


async def process_approved_executions() -> None:
    """Find approved execution records and send via bot."""
    try:
        from shared.config import get_settings
        biz = get_settings().business
        if not biz.agent_execution_live_sender_enabled:
            return
        if not biz.agent_execution_auto_execute_approved:
            return

        from infrastructure.database.session import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_execution_queue_service import (
                AgentExecutionQueueService,
            )
            queue = AgentExecutionQueueService(session)
            records = await queue.list_approved_pending(
                limit=biz.agent_execution_live_sender_batch_limit,
            )
            if not records:
                return

            from core.services.approved_execution_sender_service import (
                ApprovedExecutionSenderService,
            )

            for record in records:
                result = ApprovedExecutionSenderService.validate_before_send(
                    record,
                )
                if result.blocked:
                    if biz.agent_execution_live_sender_mark_failed_on_error:
                        await queue.mark_blocked(
                            record.execution_id,
                            result.blocked_reason or "validation_failed",
                        )
                    continue

                log.info(
                    "approved_execution_ready",
                    execution_id=record.execution_id,
                    action=record.action,
                )

            await session.commit()
    except Exception:
        log.warning("approved_execution_sender_job_error")
