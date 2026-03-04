"""Cache warm-up and maintenance jobs."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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


async def warmup_price_cache() -> None:
    """Reload pricing config from DB into Redis. TODO: implement via PricingService."""
    log.debug("cache_warmup_not_implemented")
