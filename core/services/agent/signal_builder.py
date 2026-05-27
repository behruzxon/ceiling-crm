"""
core.services.agent.signal_builder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Async I/O wrapper that loads per-user CRM data from Redis and PostgreSQL,
constructs a cached :class:`SignalVector`, and returns it.

This is the agent layer's single entry point for obtaining a normalised
signal snapshot.  It reuses the pure ``build_signal_vector()`` from
``core.services.signal_vector_service`` and adds:

- Redis AI memory loading
- Redis lead score loading
- Redis last-interaction timestamp loading
- DB lead lookup (most recent for user)
- Deal probability computation
- 5-minute Redis cache with ``force_refresh`` bypass

Import constraints
------------------
  - May import from ``core/`` and ``infrastructure/``
  - Must NOT import from ``apps/bot/handlers/``
"""
from __future__ import annotations

import time
from dataclasses import asdict
from dataclasses import fields as dc_fields

from core.services.signal_vector_service import (
    SignalVector,
    with_deal_probability,
)
from core.services.signal_vector_service import (
    build_signal_vector as _build_pure_sv,
)
from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys, CacheTTL
from shared.logging import get_logger

log = get_logger(__name__)

# Re-export for callers that only need the type.
__all__ = ["SignalVector", "load_signal_vector"]

# Valid field names for cache deserialization (forward-compat filtering).
_SV_FIELDS: frozenset[str] = frozenset(f.name for f in dc_fields(SignalVector))


# ── Public API ────────────────────────────────────────────────────────────────


async def load_signal_vector(
    user_id: int,
    *,
    lead_id: int | None = None,
    memory: dict | None = None,
    score: int | None = None,
    force_refresh: bool = False,
) -> SignalVector:
    """Load or return a cached :class:`SignalVector` for *user_id*.

    Parameters
    ----------
    user_id:
        Telegram user ID.
    lead_id:
        Specific lead ID to use.  When ``None`` the most recent lead
        for *user_id* is looked up from the database.
    memory:
        Pre-loaded Redis AI memory dict.  Avoids a Redis round-trip
        when the caller already has it (e.g. inside a handler).
    score:
        Pre-loaded 0-100 lead score.  Same rationale as *memory*.
    force_refresh:
        When ``True`` skip the cache and rebuild from scratch.

    Returns
    -------
    SignalVector
        Normalised, frozen signal container ready for any decision engine.
    """
    redis = get_redis()
    cache_key = CacheKeys.agent_signal_vector(user_id)

    # ── 1. Try cache ──────────────────────────────────────────────────
    if not force_refresh:
        cached = await _try_cache(redis, cache_key)
        if cached is not None:
            return cached

    # ── 2. Load raw data ──────────────────────────────────────────────
    if memory is None:
        memory = (await redis.get_json(CacheKeys.ai_memory(user_id))) or {}

    if score is None:
        raw_score = await redis.get(CacheKeys.ai_lead_score(user_id))
        score = int(raw_score) if raw_score else 0

    raw_ts = await redis.get(CacheKeys.ai_last_interaction(user_id))
    last_activity_ts = int(raw_ts) if raw_ts else None

    minutes_since = 0
    if last_activity_ts:
        minutes_since = max(0, int((time.time() - last_activity_ts) / 60))

    # ── 3. Load DB lead ───────────────────────────────────────────────
    lead = await _load_latest_lead(user_id, lead_id)

    # ── 4. Extract fields ─────────────────────────────────────────────
    area_m2 = _safe_float(memory.get("area_m2"))

    lead_temperature: str | None = None
    closing_confidence: float | None = None
    follow_up_count = 0
    current_stage: str | None = None
    lead_status: str | None = None

    if lead is not None:
        lead_temperature = lead.lead_temperature
        closing_confidence = lead.closing_confidence
        follow_up_count = lead.follow_up_count or 0
        current_stage = (
            lead.current_stage.value
            if hasattr(lead.current_stage, "value")
            else str(lead.current_stage)
        )
        lead_status = lead.lead_status

    # ── 5. Build pure SignalVector ─────────────────────────────────────
    sv = _build_pure_sv(
        lead_score=score,
        phone_captured=bool(memory.get("phone_captured")),
        has_area=area_m2 is not None,
        area_m2=area_m2,
        has_district=bool(memory.get("district")),
        closing_confidence=closing_confidence,
        closing_attempted=bool(memory.get("last_closing_attempt")),
        closing_action=memory.get("last_closing_attempt"),
        last_objection=memory.get("last_objection"),
        last_objection_severity=memory.get("last_objection_severity"),
        lead_temperature=lead_temperature,
        buyer_type=memory.get("buyer_type"),
        current_stage=current_stage,
        design_type=memory.get("design_type"),
        lead_status=lead_status,
        follow_up_count=follow_up_count,
        minutes_since_last_activity=minutes_since,
        last_activity_ts=last_activity_ts,
        negotiation_escalated=bool(memory.get("negotiation_escalated")),
    )

    # ── 6. Compute deal probability ────────────────────────────────────
    try:
        from shared.utils.deal_probability import evaluate_deal_probability

        dp = evaluate_deal_probability(signal_vector=sv)
        sv = with_deal_probability(sv, dp.deal_probability_percent)
    except Exception:
        log.warning("agent_sv_deal_prob_error", user_id=user_id, exc_info=True)

    # ── 7. Cache result ────────────────────────────────────────────────
    try:
        await redis.set_json(
            cache_key,
            asdict(sv),
            ttl=CacheTTL.AGENT_SIGNAL_VECTOR,
        )
    except Exception:
        log.warning("agent_sv_cache_write_error", user_id=user_id)

    log.debug("agent_sv_built", user_id=user_id, score=score, prob=sv.deal_probability_percent)
    return sv


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _try_cache(redis: object, cache_key: str) -> SignalVector | None:
    """Attempt to deserialize a cached SignalVector, returning None on miss."""
    try:
        cached = await redis.get_json(cache_key)  # type: ignore[union-attr]
        if cached is None:
            return None
        # Filter to valid fields only (forward compatibility).
        filtered = {k: v for k, v in cached.items() if k in _SV_FIELDS}
        return SignalVector(**filtered)
    except Exception:
        log.debug("agent_sv_cache_miss", key=cache_key)
        return None


async def _load_latest_lead(
    user_id: int,
    lead_id: int | None,
) -> object | None:
    """Load the most recent lead for *user_id* from the database.

    Opens its own short-lived session (same pattern as
    ``FollowupService`` and ``LeadNotificationService``).
    """
    try:
        from infrastructure.database.repositories.lead_repo import (
            PostgresLeadRepository,
        )
        from infrastructure.database.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            if lead_id is not None:
                return await repo.get_by_id(lead_id)
            leads = await repo.list_by_user(user_id, limit=1)
            return leads[0] if leads else None
    except Exception:
        log.warning("agent_sv_lead_load_error", user_id=user_id, exc_info=True)
        return None


def _safe_float(val: object) -> float | None:
    """Convert *val* to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None
