"""Cache warm-up and maintenance jobs."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from infrastructure.cache.distributed_lock import scheduler_lock
from shared.logging import get_logger

log = get_logger(__name__)


def register_cache_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        warmup_price_cache,
        trigger="interval",
        minutes=30,
        id="cache_warmup",
        replace_existing=True,
    )


@scheduler_lock("cache_warmup")
async def warmup_price_cache() -> None:
    """Reload pricing config from DB into Redis. TODO: implement via PricingService."""
    log.debug("cache_warmup_not_implemented")
