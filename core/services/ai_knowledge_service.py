"""
core.services.ai_knowledge_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Loads tenant AI knowledge entries and builds a context block
for injection into the system prompt.

Includes Redis caching with 10-minute TTL to avoid hitting DB
on every AI call.

Usage::

    from core.services.ai_knowledge_service import (
        get_tenant_knowledge_block,
        invalidate_tenant_knowledge_cache,
    )

    block = await get_tenant_knowledge_block(tenant_id, user_text)
    # block is a string like "## Services\n- Title: content\n..." or ""
"""
from __future__ import annotations

import json
import re
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

CACHE_TTL = 600  # 10 minutes
_MAX_ENTRIES = 50  # max entries per tenant to cache
_TOP_K = 5  # max entries to inject per AI call


# ── Keyword extraction (simple) ────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "va", "bilan", "uchun", "bu", "shu", "u", "men", "siz", "nima",
    "qanday", "qancha", "narx", "bo'ladi", "kerak", "haqida",
    "и", "в", "на", "что", "как", "это", "для", "не", "да", "нет",
    "the", "a", "an", "is", "are", "what", "how", "much",
})

_WORD_RE = re.compile(r"\w{3,}", re.UNICODE)


def extract_keywords(text: str, max_keywords: int = 6) -> list[str]:
    """Extract meaningful keywords from user text for knowledge search."""
    words = _WORD_RE.findall(text.lower())
    return [w for w in words if w not in _STOP_WORDS][:max_keywords]


# ── Cache helpers ──────────────────────────────────────────────────────────

def _cache_key(tenant_id: int) -> str:
    return f"ai_kb:{tenant_id}"


async def _get_cached_entries(tenant_id: int) -> list[dict[str, Any]] | None:
    """Get all knowledge entries for a tenant from Redis cache."""
    try:
        from infrastructure.cache.client import get_redis
        cache = get_redis()
        raw = await cache.get(_cache_key(tenant_id))
        if raw is not None:
            return json.loads(raw)
        return None
    except Exception:
        log.warning("ai_kb_cache_get_failed", tenant_id=tenant_id)
        return None


async def _set_cached_entries(tenant_id: int, entries: list[dict[str, Any]]) -> None:
    """Store all knowledge entries for a tenant in Redis cache."""
    try:
        from infrastructure.cache.client import get_redis
        cache = get_redis()
        serialized = json.dumps(entries, ensure_ascii=False, default=str)
        await cache.set(_cache_key(tenant_id), serialized, ttl=CACHE_TTL)
    except Exception:
        log.warning("ai_kb_cache_set_failed", tenant_id=tenant_id)


async def invalidate_tenant_knowledge_cache(tenant_id: int) -> None:
    """Remove cached knowledge for a tenant (call after add/update/delete)."""
    try:
        from infrastructure.cache.client import get_redis
        cache = get_redis()
        await cache.delete(_cache_key(tenant_id))
    except Exception:
        log.warning("ai_kb_cache_invalidate_failed", tenant_id=tenant_id)


# ── Knowledge block builder ───────────────────────────────────────────────

def _score_entry(entry: dict[str, Any], keywords: list[str]) -> int:
    """Score an entry based on keyword overlap with title+content."""
    if not keywords:
        return 0
    text = f"{entry.get('title', '')} {entry.get('content', '')}".lower()
    return sum(1 for kw in keywords if kw in text)


def _build_block(entries: list[dict[str, Any]]) -> str:
    """Format knowledge entries as a text block for system prompt injection."""
    if not entries:
        return ""

    lines: list[str] = ["", "========================", "BIZNES BILIMLAR", "========================"]
    current_cat = ""
    for e in entries:
        cat = e.get("category", "")
        if cat != current_cat:
            current_cat = cat
            lines.append(f"\n## {cat}")
        lines.append(f"- {e['title']}: {e['content']}")

    return "\n".join(lines)


async def get_tenant_knowledge_block(
    tenant_id: int | None,
    user_text: str = "",
) -> str:
    """Build a knowledge context block for a tenant's AI call.

    1. Checks Redis cache for all tenant knowledge entries
    2. If miss, loads from DB and caches for 10 min
    3. Scores entries against user message keywords
    4. Returns top-K formatted as text block (or "" if no entries)

    Returns empty string when tenant_id is None or tenant has no knowledge.
    """
    if not tenant_id:
        return ""

    # Try cache first
    entries = await _get_cached_entries(tenant_id)

    if entries is None:
        # Load from DB
        try:
            from infrastructure.database.session import get_session_factory
            from infrastructure.database.repositories.ai_knowledge_repo import (
                PostgresAiKnowledgeRepository,
            )

            session_factory = get_session_factory()
            async with session_factory() as session:
                repo = PostgresAiKnowledgeRepository(session)
                domain_entries = await repo.get_by_tenant(tenant_id)
                entries = [
                    {
                        "id": e.id,
                        "category": e.category,
                        "title": e.title,
                        "content": e.content,
                    }
                    for e in domain_entries[:_MAX_ENTRIES]
                ]
                await _set_cached_entries(tenant_id, entries)
        except Exception:
            log.warning("ai_kb_load_failed", tenant_id=tenant_id)
            return ""

    if not entries:
        return ""

    # Score and select top-K
    keywords = extract_keywords(user_text)
    if keywords:
        scored = [(e, _score_entry(e, keywords)) for e in entries]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = [e for e, s in scored[:_TOP_K]]
    else:
        # No keywords — return first _TOP_K entries
        top = entries[:_TOP_K]

    return _build_block(top)
