"""
core.services.usage_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tracks and enforces per-tenant usage limits based on subscription plan.

Uses Redis counters for real-time tracking (leads/month, AI messages/day)
and plan configuration from ``shared.constants.plans`` for limit enforcement.

Fails open: if Redis is unreachable or plan lookup fails, the action is allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from shared.constants.plans import PlanConfig, get_plan_config
from shared.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class UsageStatus:
    """Current usage snapshot for a tenant."""

    plan_name: str
    leads_used: int
    leads_limit: int  # 0 = unlimited
    ai_messages_used: int
    ai_messages_limit: int  # 0 = unlimited

    @property
    def leads_remaining(self) -> int | None:
        """None means unlimited."""
        if self.leads_limit == 0:
            return None
        return max(0, self.leads_limit - self.leads_used)

    @property
    def ai_remaining(self) -> int | None:
        if self.ai_messages_limit == 0:
            return None
        return max(0, self.ai_messages_limit - self.ai_messages_used)


@dataclass(slots=True)
class LimitCheckResult:
    """Result of a usage limit check."""

    allowed: bool
    reason: str | None = None  # human-readable denial message (Uzbek)
    used: int = 0
    limit: int = 0


async def check_lead_limit(
    tenant_id: int,
    plan_name: str | None = None,
) -> LimitCheckResult:
    """Check if the tenant can create another lead this month.

    Fails open if Redis is unreachable.
    """
    try:
        config = get_plan_config(plan_name)
        if config.leads_per_month == 0:
            return LimitCheckResult(allowed=True)

        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        now = datetime.now(timezone.utc)
        ym = now.strftime("%Y-%m")
        key = CacheKeys.monthly_lead_count(tenant_id, year_month=ym)
        cache = get_redis()

        raw = await cache.get(key)
        used = int(raw) if raw else 0

        if used >= config.leads_per_month:
            log.warning(
                "lead_limit_exceeded",
                tenant_id=tenant_id,
                plan=config.name,
                used=used,
                limit=config.leads_per_month,
            )
            return LimitCheckResult(
                allowed=False,
                reason=(
                    f"Oylik lid limiti tugadi ({used}/{config.leads_per_month}).\n"
                    f"Rejangizni yangilang: /subscription"
                ),
                used=used,
                limit=config.leads_per_month,
            )

        return LimitCheckResult(allowed=True, used=used, limit=config.leads_per_month)

    except Exception:
        log.warning("lead_limit_check_failed", tenant_id=tenant_id)
        return LimitCheckResult(allowed=True)


async def check_ai_limit(
    tenant_id: int,
    plan_name: str | None = None,
) -> LimitCheckResult:
    """Check if the tenant can make another AI call today.

    This is separate from the per-user rate limit in ai_openai.py.
    Fails open if Redis is unreachable.
    """
    try:
        config = get_plan_config(plan_name)
        if config.ai_messages_per_day == 0:
            return LimitCheckResult(allowed=True)

        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        key = CacheKeys.ai_daily_quota(tenant_id, date_str=date_str)
        cache = get_redis()

        raw = await cache.get(key)
        used = int(raw) if raw else 0

        if used >= config.ai_messages_per_day:
            log.warning(
                "ai_limit_exceeded",
                tenant_id=tenant_id,
                plan=config.name,
                used=used,
                limit=config.ai_messages_per_day,
            )
            return LimitCheckResult(
                allowed=False,
                reason=(
                    f"Kunlik AI xabar limiti tugadi ({used}/{config.ai_messages_per_day}).\n"
                    f"Rejangizni yangilang: /subscription"
                ),
                used=used,
                limit=config.ai_messages_per_day,
            )

        return LimitCheckResult(allowed=True, used=used, limit=config.ai_messages_per_day)

    except Exception:
        log.warning("ai_limit_check_failed", tenant_id=tenant_id)
        return LimitCheckResult(allowed=True)


def check_feature(
    plan_name: str | None,
    feature: str,
) -> LimitCheckResult:
    """Check if a feature is enabled for the given plan.

    Supported features: 'knowledge_base', 'operator_assignment', 'analytics'.
    """
    config = get_plan_config(plan_name)
    feature_map = {
        "knowledge_base": config.knowledge_base_enabled,
        "operator_assignment": config.operator_assignment_enabled,
        "analytics": config.analytics_enabled,
    }
    enabled = feature_map.get(feature, True)
    if not enabled:
        return LimitCheckResult(
            allowed=False,
            reason=(
                f"Bu funksiya sizning rejangizda mavjud emas ({config.display_name}).\n"
                f"Rejangizni yangilang: /subscription"
            ),
        )
    return LimitCheckResult(allowed=True)


async def track_lead_created(tenant_id: int) -> None:
    """Increment the monthly lead counter for a tenant."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        now = datetime.now(timezone.utc)
        ym = now.strftime("%Y-%m")
        key = CacheKeys.monthly_lead_count(tenant_id, year_month=ym)
        cache = get_redis()

        count = await cache.incr(key)
        if count == 1:
            await cache.expire(key, CacheTTL.MONTHLY_LEAD_COUNTER)

    except Exception:
        log.warning("track_lead_failed", tenant_id=tenant_id)


async def get_usage_summary(
    tenant_id: int,
    plan_name: str | None = None,
) -> UsageStatus:
    """Build a usage snapshot for display in the subscription UI."""
    config = get_plan_config(plan_name)

    leads_used = 0
    ai_used = 0

    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        cache = get_redis()
        now = datetime.now(timezone.utc)

        # Monthly leads
        ym = now.strftime("%Y-%m")
        raw_leads = await cache.get(CacheKeys.monthly_lead_count(tenant_id, year_month=ym))
        leads_used = int(raw_leads) if raw_leads else 0

        # Daily AI
        date_str = now.strftime("%Y-%m-%d")
        raw_ai = await cache.get(CacheKeys.ai_daily_quota(tenant_id, date_str=date_str))
        ai_used = int(raw_ai) if raw_ai else 0

    except Exception:
        log.warning("usage_summary_failed", tenant_id=tenant_id)

    return UsageStatus(
        plan_name=config.name,
        leads_used=leads_used,
        leads_limit=config.leads_per_month,
        ai_messages_used=ai_used,
        ai_messages_limit=config.ai_messages_per_day,
    )


async def reset_monthly_usage(tenant_id: int) -> None:
    """Reset the monthly lead counter (called on billing cycle reset)."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        cache = get_redis()
        now = datetime.now(timezone.utc)
        ym = now.strftime("%Y-%m")
        key = CacheKeys.monthly_lead_count(tenant_id, year_month=ym)
        await cache.delete(key)

        log.info("usage_reset", tenant_id=tenant_id, month=ym)

    except Exception:
        log.warning("usage_reset_failed", tenant_id=tenant_id)
