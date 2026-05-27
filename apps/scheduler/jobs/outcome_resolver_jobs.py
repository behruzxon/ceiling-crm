"""Outcome resolver + adaptive weights refresh scheduler jobs."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_outcome_resolver_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register outcome resolution and adaptive weights jobs."""
    # Resolve pending outcomes every 5 minutes
    scheduler.add_job(
        resolve_tactic_outcomes,
        trigger="interval",
        minutes=5,
        id="resolve_tactic_outcomes",
        replace_existing=True,
    )
    # Refresh adaptive weights every 1 hour
    scheduler.add_job(
        refresh_adaptive_weights,
        trigger="interval",
        hours=1,
        id="refresh_adaptive_weights",
        replace_existing=True,
    )


async def resolve_tactic_outcomes() -> None:
    """Resolve pending AI tactic outcomes by checking lead progression."""
    from core.services.outcome_resolver_service import OutcomeResolverService

    svc = OutcomeResolverService()
    count = await svc.resolve_pending_outcomes()
    if count:
        log.info("outcome_resolver_done", resolved=count)


async def refresh_adaptive_weights() -> None:
    """Query resolved stats, compute adaptive weights, cache to Redis."""
    import json

    from core.services.adaptive_weights_service import compute_adaptive_weights
    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys, CacheTTL
    from infrastructure.database.session import get_session_factory
    from infrastructure.di import get_tactic_outcome_repo

    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = get_tactic_outcome_repo(session)
            stats = await repo.get_resolved_stats(min_samples=5)

        weights = compute_adaptive_weights(stats)

        if not weights.data_sufficient:
            log.debug("adaptive_weights_insufficient_data")
            return

        redis = get_redis()
        ttl = CacheTTL.ADAPTIVE_WEIGHTS

        # Cache per event type
        for event_type, w in [
            ("negotiation", weights.negotiation_weights),
            ("closer", weights.closer_weights),
            ("followup", weights.followup_weights),
        ]:
            if w:
                key = CacheKeys.adaptive_weights(event_type)
                await redis.set(key, json.dumps(w), ttl=ttl)

        log.info(
            "adaptive_weights_refreshed",
            negotiation=len(weights.negotiation_weights),
            closer=len(weights.closer_weights),
            followup=len(weights.followup_weights),
        )
    except Exception:
        log.exception("adaptive_weights_refresh_error")
