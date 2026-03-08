"""
core.services.ai_cache_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Redis-backed response cache for AI (OpenAI) calls.

Caches FAQ-like responses per tenant to reduce API spend.
Only caches short, non-PII messages from first-contact conversations
(no history).

Usage::

    from core.services.ai_cache_service import get_cached_response, store_response

    cached = await get_cached_response(tenant_id, user_text)
    if cached is not None:
        result = cached   # cache hit
    else:
        result = await _call_ai(...)
        await store_response(tenant_id, user_text, result, cacheable=True)
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

CACHE_TTL = 86_400          # 24 hours
MAX_CACHEABLE_LEN = 500     # skip messages longer than this

# ── PII detection patterns ───────────────────────────────────────────────────
# Messages matching any of these are never cached.

_PHONE_RE = re.compile(
    r"\+?(?:998)?\s*\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)

_ORDER_ID_RE = re.compile(
    r"(?:order|zakaz|buyurtma|заказ)[#_\s\-]*\d{3,}",
    re.IGNORECASE,
)

# Common Uzbek/Russian first names (short list for heuristic detection).
# Only matches when the name appears to be self-identification, e.g.
# "mening ismim Alisher" or "menya zovut Dima".
_NAME_INTRO_RE = re.compile(
    r"(?:ismim|mening\s+ismim|menya\s+zovut|my\s+name\s+is)\s+\S+",
    re.IGNORECASE,
)

# Standalone digits that look like IDs (6+ digit sequences)
_NUMERIC_ID_RE = re.compile(r"\b\d{6,}\b")


# ── Key builder ──────────────────────────────────────────────────────────────

def _cache_key(tenant_id: int | None, message: str) -> str:
    """Build Redis key: ai_cache:{tenant_id}:{sha256(normalized_message)}."""
    normalized = message.strip().lower()
    msg_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    tid = tenant_id or 0
    return f"ai_cache:{tid}:{msg_hash}"


# ── Cacheability check ──────────────────────────────────────────────────────

def is_cacheable(message: str, *, has_history: bool = False) -> bool:
    """Determine whether a message+response pair should be cached.

    Returns False for:
    - Messages longer than 500 characters
    - Messages containing phone numbers, order IDs, name introductions
    - Conversations with existing history (context-dependent responses)
    """
    if has_history:
        return False
    if len(message) > MAX_CACHEABLE_LEN:
        return False
    if _PHONE_RE.search(message):
        return False
    if _ORDER_ID_RE.search(message):
        return False
    if _NAME_INTRO_RE.search(message):
        return False
    if _NUMERIC_ID_RE.search(message):
        return False
    return True


# ── Public API ───────────────────────────────────────────────────────────────

async def get_cached_response(
    tenant_id: int | None,
    user_text: str,
    *,
    has_history: bool = False,
) -> dict[str, Any] | None:
    """Look up a cached AI response.

    Returns the cached JSON dict or None on miss.
    Fails silently — never raises.
    """
    if not is_cacheable(user_text, has_history=has_history):
        return None

    try:
        from infrastructure.cache.client import get_redis

        cache = get_redis()
        key = _cache_key(tenant_id, user_text)
        raw = await cache.get(key)
        if raw is not None:
            log.debug("ai_cache_hit", tenant_id=tenant_id, key=key)
            return json.loads(raw)

        log.debug("ai_cache_miss", tenant_id=tenant_id, key=key)
        return None

    except Exception:
        log.warning("ai_cache_get_failed", tenant_id=tenant_id)
        return None


async def store_response(
    tenant_id: int | None,
    user_text: str,
    response: dict[str, Any],
    *,
    has_history: bool = False,
) -> None:
    """Store an AI response in cache.

    No-op if the message is not cacheable. Fails silently — never raises.
    """
    if not is_cacheable(user_text, has_history=has_history):
        return

    try:
        from infrastructure.cache.client import get_redis

        cache = get_redis()
        key = _cache_key(tenant_id, user_text)
        serialized = json.dumps(response, ensure_ascii=False, default=str)
        await cache.set(key, serialized, ttl=CACHE_TTL)
        log.debug("ai_cache_stored", tenant_id=tenant_id, key=key)

    except Exception:
        log.warning("ai_cache_store_failed", tenant_id=tenant_id)
