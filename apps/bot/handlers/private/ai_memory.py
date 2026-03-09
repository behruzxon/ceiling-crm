"""
apps.bot.handlers.private.ai_memory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Redis-backed per-user AI memory and daily stats counters.

Cross-module dependencies are lazy-imported inside functions to avoid
circular imports with ``ai_scoring`` and ``ai_detection``.
"""
from __future__ import annotations

import time
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)


# ── Redis AI memory (30-day per-user context) ────────────────────────────────

async def _load_ai_memory(user_id: int, *, bot_id: int | None = None) -> dict[str, Any]:
    """Load per-user AI memory from Redis. Returns {} on any error."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys
        return (await get_redis().get_json(CacheKeys.ai_memory(user_id, bot_id=bot_id))) or {}
    except Exception:
        return {}


async def _save_ai_memory(user_id: int, memory: dict[str, Any], *, bot_id: int | None = None) -> None:
    """Persist AI memory to Redis with 30-day TTL. Never raises."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL
        now = int(time.time())
        if "created_at" not in memory:
            memory["created_at"] = now
        memory["updated_at"] = now
        await get_redis().set_json(CacheKeys.ai_memory(user_id, bot_id=bot_id), memory, ttl=CacheTTL.AI_MEMORY)
    except Exception:
        pass


def _build_greeting_from_memory(memory: dict[str, Any]) -> str:
    """Build a personalised greeting using stored user context."""
    name = memory.get("name", "")
    district = memory.get("district")
    area = memory.get("area_m2")
    phone_captured = memory.get("phone_captured", False)
    if phone_captured:
        return (
            f"Salom yana {name} 🙂\n\n"
            "Zakazingiz bo'yicha yoki boshqa savol bormi?"
        )
    if district and area:
        return (
            f"Salom {name} 🙂\n\n"
            f"{district}dagi {area:g} m² potolok bo'yicha savolingiz bormi?"
        )
    if district:
        return f"Salom {name} 🙂\n\n{district}dagi xonadoningiz uchun nima kerak?"
    return f"Salom {name} 🙂\n\nPotolok bo'yicha yordam kerakmi?"


async def _update_ai_memory_from_interaction(
    user_id: int,
    *,
    text: str,
    fsm_data: dict[str, Any],
    first_name: str | None = None,
    bot_id: int | None = None,
) -> None:
    """Extract context from text + FSM and merge into Redis AI memory. Never raises."""
    try:
        # Lazy imports to avoid circular deps
        from apps.bot.handlers.private.ai_detection import parse_combo
        from apps.bot.handlers.private.ai_scoring import _get_lead_score

        memory = await _load_ai_memory(user_id, bot_id=bot_id)

        # Name from FSM; fallback to Telegram first_name on first interaction
        if name := (fsm_data.get("user_name") or ""):
            memory["name"] = name
        elif first_name and not memory.get("name"):
            memory["name"] = first_name

        # Parse combo: district, area_m2, design_type from current message
        combo = parse_combo(text)
        if combo.get("district"):
            memory["district"] = combo["district"]
        if combo.get("area") is not None:
            memory["area_m2"] = combo["area"]
        if combo.get("design"):
            memory["design_type"] = combo["design"]

        # FSM data fallbacks (set earlier in this session)
        if not memory.get("district") and (d := fsm_data.get("price_district")):
            memory["district"] = d
        if not memory.get("area_m2") and (a := fsm_data.get("price_area")):
            memory["area_m2"] = a
        if not memory.get("design_type") and (dsg := fsm_data.get("price_design")):
            memory["design_type"] = dsg

        # Lead score
        score = await _get_lead_score(user_id, bot_id=bot_id)
        if score > 0:
            memory["lead_score"] = score

        # Last message
        memory["last_user_message"] = text[:200]

        await _save_ai_memory(user_id, memory, bot_id=bot_id)
    except Exception:
        log.warning("update_ai_memory_failed", user_id=user_id)


# ── Daily AI stats counters (Redis INCR, date-keyed) ────────────────────────

_AI_STATS_FIELDS = frozenset({
    "users_started", "messages_total",
    "lead_hot", "lead_warm", "lead_cold",
    "phones_received", "orders_started",
})


async def _ai_stats_incr(field: str, *, bot_id: int | None = None) -> None:
    """Increment today's AI stats counter by 1. Non-fatal, fire-and-forget."""
    import datetime
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL
        date_str = datetime.date.today().isoformat()
        redis = get_redis()
        key = CacheKeys.ai_stats_field(date_str, field, bot_id=bot_id)
        await redis.incr_with_ttl(key, CacheTTL.AI_STATS)
    except Exception:
        pass


async def _ai_stats_count_user(user_id: int, *, bot_id: int | None = None) -> None:
    """Increment users_started once per user per calendar day (NX dedup). Non-fatal."""
    import datetime
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL
        date_str = datetime.date.today().isoformat()
        redis = get_redis()
        acquired = await redis.set(
            CacheKeys.ai_stats_user_day(date_str, user_id, bot_id=bot_id),
            "1",
            ttl=CacheTTL.AI_STATS_USER_DAY,
            nx=True,
        )
        if acquired:
            key = CacheKeys.ai_stats_field(date_str, "users_started", bot_id=bot_id)
            await redis.incr_with_ttl(key, CacheTTL.AI_STATS)
    except Exception:
        pass
