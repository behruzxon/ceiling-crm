"""
core.security.rate_limiter
~~~~~~~~~~~~~~~~~~~~~~~~~~
Unified rate limiting for the SaaS platform.

Three tiers of protection:
1. **Per-user message limit** — prevents individual spam
2. **Per-tenant message limit** — protects shared resources
3. **Per-tenant AI call limit** — controls OpenAI API spend

All limits use Redis sliding-window counters (sorted sets).
Admin/superadmin users bypass all limits.

Usage::

    from core.security.rate_limiter import check_rate_limits

    result = await check_rate_limits(
        user_id=123, tenant_id=1, is_ai_request=True,
    )
    if not result.allowed:
        # reply with result.denial_message, optionally log
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared.logging import get_logger

log = get_logger(__name__)


# ── Denial reasons ───────────────────────────────────────────────────────────

class DenialReason(str, Enum):
    USER_MESSAGE = "user_message"     # per-user message flood
    TENANT_MESSAGE = "tenant_message" # tenant-wide message flood
    AI_TENANT = "ai_tenant"           # per-tenant AI call limit


# ── Result ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate limit check."""

    allowed: bool
    reason: DenialReason | None = None
    remaining: int | None = None

    @property
    def denial_message(self) -> str:
        return (
            "Juda ko'p so'rov yuboryapsiz. "
            "Iltimos bir oz kuting."
        )


# ── Limits (defaults, overridable via settings if needed) ────────────────────

USER_MSG_WINDOW = 30        # seconds
USER_MSG_MAX = 10           # 10 messages per 30 seconds

TENANT_MSG_WINDOW = 60      # seconds
TENANT_MSG_MAX = 100        # 100 messages per minute

AI_TENANT_WINDOW = 60       # seconds
AI_TENANT_MAX = 30          # 30 AI calls per minute per tenant


# ── Key builders (registered in CacheKeys for discoverability) ───────────────

def _user_msg_key(tenant_id: int | None, user_id: int) -> str:
    tid = tenant_id or 0
    return f"rate:user:{tid}:{user_id}"


def _tenant_msg_key(tenant_id: int) -> str:
    return f"rate:tenant:{tenant_id}"


def _ai_tenant_key(tenant_id: int) -> str:
    return f"rate:ai:{tenant_id}"


# ── Public API ───────────────────────────────────────────────────────────────

async def check_rate_limits(
    user_id: int,
    tenant_id: int | None = None,
    *,
    is_ai_request: bool = False,
    is_admin: bool = False,
) -> RateLimitResult:
    """Run all applicable rate limit checks.

    Args:
        user_id: Telegram user ID.
        tenant_id: Current tenant (None = single-tenant mode).
        is_ai_request: True if this message will trigger an OpenAI call.
        is_admin: True for ADMIN/SUPERADMIN roles — bypasses all limits.

    Returns:
        ``RateLimitResult`` — check ``.allowed`` before proceeding.

    Fails open: if Redis is unreachable, the request is allowed.
    """
    if is_admin:
        return RateLimitResult(allowed=True)

    try:
        from infrastructure.cache.client import get_redis

        cache = get_redis()

        # 1. Per-user message limit
        key = _user_msg_key(tenant_id, user_id)
        allowed, remaining = await cache.rate_limit_check(
            identifier=key,
            window_seconds=USER_MSG_WINDOW,
            max_requests=USER_MSG_MAX,
        )
        if not allowed:
            log.warning(
                "rate_limit_user_msg",
                user_id=user_id,
                tenant_id=tenant_id,
                remaining=remaining,
            )
            return RateLimitResult(
                allowed=False,
                reason=DenialReason.USER_MESSAGE,
                remaining=remaining,
            )

        # 2. Per-tenant message limit
        if tenant_id is not None:
            key = _tenant_msg_key(tenant_id)
            allowed, remaining = await cache.rate_limit_check(
                identifier=key,
                window_seconds=TENANT_MSG_WINDOW,
                max_requests=TENANT_MSG_MAX,
            )
            if not allowed:
                log.warning(
                    "rate_limit_tenant_msg",
                    tenant_id=tenant_id,
                    remaining=remaining,
                )
                return RateLimitResult(
                    allowed=False,
                    reason=DenialReason.TENANT_MESSAGE,
                    remaining=remaining,
                )

        # 3. Per-tenant AI call limit
        if is_ai_request and tenant_id is not None:
            key = _ai_tenant_key(tenant_id)
            allowed, remaining = await cache.rate_limit_check(
                identifier=key,
                window_seconds=AI_TENANT_WINDOW,
                max_requests=AI_TENANT_MAX,
            )
            if not allowed:
                log.warning(
                    "rate_limit_ai_tenant",
                    tenant_id=tenant_id,
                    remaining=remaining,
                )
                return RateLimitResult(
                    allowed=False,
                    reason=DenialReason.AI_TENANT,
                    remaining=remaining,
                )

        return RateLimitResult(allowed=True)

    except Exception:
        log.warning("rate_limit_check_failed", user_id=user_id)
        return RateLimitResult(allowed=True)  # fail open
