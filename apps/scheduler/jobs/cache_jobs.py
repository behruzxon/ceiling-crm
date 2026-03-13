"""Cache warm-up and maintenance jobs."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)

_CONVERSATION_RETENTION_DAYS = 90


def register_cache_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        warmup_price_cache,
        trigger="interval",
        minutes=30,
        id="cache_warmup",
        replace_existing=True,
    )
    scheduler.add_job(
        cleanup_old_conversations,
        trigger="cron",
        hour=4,
        minute=0,
        id="cleanup_old_conversations",
        replace_existing=True,
    )


async def warmup_price_cache() -> None:
    """Reload pricing config from DB into Redis. TODO: implement via PricingService."""
    log.debug("cache_warmup_not_implemented")


async def cleanup_old_conversations() -> None:
    """Delete ai_conversations rows older than 90 days in batches."""
    from datetime import datetime, timedelta, timezone

    import sqlalchemy as sa

    from infrastructure.database.models.ai_conversation import AiConversationModel
    from infrastructure.database.session import get_session_factory

    cutoff = datetime.now(timezone.utc) - timedelta(days=_CONVERSATION_RETENTION_DAYS)
    batch_size = 1000
    total_deleted = 0

    log.info("conversation_cleanup_started", cutoff=str(cutoff))
    try:
        factory = get_session_factory()
        while True:
            async with factory() as session:
                # Select IDs in batch to avoid long-running DELETE locks
                ids_result = await session.execute(
                    sa.select(AiConversationModel.id)
                    .where(AiConversationModel.updated_at < cutoff)
                    .limit(batch_size)
                )
                ids = ids_result.scalars().all()
                if not ids:
                    break

                await session.execute(
                    sa.delete(AiConversationModel).where(
                        AiConversationModel.id.in_(ids),
                    )
                )
                await session.commit()
                total_deleted += len(ids)

                if len(ids) < batch_size:
                    break
    except Exception:
        log.exception("conversation_cleanup_failed", deleted_so_far=total_deleted)
        return

    if total_deleted:
        log.info("old_conversations_cleaned", deleted=total_deleted, cutoff=str(cutoff))
    else:
        log.debug("conversation_cleanup_nothing_to_delete")
