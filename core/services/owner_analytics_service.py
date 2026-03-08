"""
core.services.owner_analytics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tenant-scoped analytics aggregation for the owner dashboard.

Pulls metrics from PostgreSQL (leads, pipeline stages) and Redis
(AI quota counters, cache stats) and returns a structured payload.
Results are cached per tenant+window for 60 seconds.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

_TERMINAL_STATUSES = frozenset({"deal", "lost"})


# ── Result data classes ──────────────────────────────────────────────────────


@dataclass(slots=True)
class LeadFunnelMetrics:
    leads_today: int = 0
    leads_7d: int = 0
    leads_30d: int = 0
    hot_leads: int = 0
    warm_leads: int = 0
    cold_leads: int = 0
    total_leads: int = 0
    won_leads: int = 0
    lost_leads: int = 0
    active_leads: int = 0
    conversion_rate: float = 0.0  # won / total


@dataclass(slots=True)
class OperatorMetrics:
    assigned_leads: int = 0
    unassigned_leads: int = 0
    attention_queue: int = 0
    operators_count: int = 0


@dataclass(slots=True)
class AIMetrics:
    ai_messages_today: int = 0
    ai_messages_7d: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    cache_hit_rate: float = 0.0


@dataclass(slots=True)
class FollowUpMetrics:
    followups_scheduled: int = 0
    followups_reengaged: int = 0  # user_followup_stage > 0
    followups_closed: int = 0     # user_followup_closed
    avg_followup_count: float = 0.0


@dataclass(slots=True)
class OwnerAnalytics:
    """Complete analytics payload for one tenant + time window."""
    window_days: int = 1
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    funnel: LeadFunnelMetrics = field(default_factory=LeadFunnelMetrics)
    operators: OperatorMetrics = field(default_factory=OperatorMetrics)
    ai: AIMetrics = field(default_factory=AIMetrics)
    followups: FollowUpMetrics = field(default_factory=FollowUpMetrics)


# ── Public API ───────────────────────────────────────────────────────────────


async def get_owner_analytics(
    tenant_id: int,
    window_days: int = 1,
) -> OwnerAnalytics:
    """Build tenant-scoped analytics. Uses 60s Redis cache.

    Args:
        tenant_id: The tenant to aggregate for.
        window_days: 1 (today), 7, or 30.

    Returns:
        OwnerAnalytics dataclass.
    """
    # Try cache first
    cached = await _get_cached(tenant_id, window_days)
    if cached is not None:
        return cached

    try:
        result = await _build_analytics(tenant_id, window_days)
    except Exception:
        log.warning("owner_analytics_build_failed", tenant_id=tenant_id, window=window_days)
        result = OwnerAnalytics(window_days=window_days)

    await _set_cached(tenant_id, window_days, result)
    return result


# ── Internal builders ────────────────────────────────────────────────────────


async def _build_analytics(tenant_id: int, window_days: int) -> OwnerAnalytics:
    """Aggregate all metrics from PostgreSQL + Redis."""
    from infrastructure.database.session import get_session_factory
    from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
    from infrastructure.di import get_user_service
    from sqlalchemy import select, func
    from infrastructure.database.models.lead import LeadModel

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    factory = get_session_factory()
    async with factory() as session:
        repo = PostgresLeadRepository(session, tenant_id)

        # ── Lead funnel from DB ──────────────────────────────────────
        funnel = await _build_funnel_metrics(session, tenant_id, window_start, today_start)

        # ── Operator metrics ─────────────────────────────────────────
        operators = await _build_operator_metrics(session, repo, tenant_id)

        # ── Follow-up metrics ────────────────────────────────────────
        followups = await _build_followup_metrics(session, tenant_id, window_start)

        # ── Operator count ───────────────────────────────────────────
        try:
            svc = get_user_service(session, tenant_id)
            managers = await svc.get_managers()
            operators.operators_count = len(managers)
        except Exception:
            pass

    # ── AI metrics from Redis ────────────────────────────────────────
    ai = await _build_ai_metrics(tenant_id, window_days, today_start)

    return OwnerAnalytics(
        window_days=window_days,
        funnel=funnel,
        operators=operators,
        ai=ai,
        followups=followups,
    )


async def _build_funnel_metrics(
    session: Any,
    tenant_id: int,
    window_start: datetime,
    today_start: datetime,
) -> LeadFunnelMetrics:
    """Aggregate lead funnel from PostgreSQL."""
    from sqlalchemy import select, func, case, and_
    from infrastructure.database.models.lead import LeadModel

    m = LeadFunnelMetrics()

    # Single aggregation query for all lead counts
    stmt = (
        select(
            func.count().label("total"),
            func.count().filter(LeadModel.created_at >= today_start).label("today"),
            func.count().filter(
                LeadModel.created_at >= (datetime.now(timezone.utc) - timedelta(days=7)),
            ).label("d7"),
            func.count().filter(LeadModel.lead_temperature == "hot").label("hot"),
            func.count().filter(LeadModel.lead_temperature == "warm").label("warm"),
            func.count().filter(LeadModel.lead_temperature == "cold").label("cold"),
            func.count().filter(LeadModel.lead_status == "deal").label("won"),
            func.count().filter(LeadModel.lead_status == "lost").label("lost"),
            func.count().filter(
                LeadModel.lead_status.notin_(["deal", "lost"])
                | LeadModel.lead_status.is_(None),
            ).label("active"),
        )
        .where(LeadModel.tenant_id == tenant_id)
    )

    result = await session.execute(stmt)
    row = result.one()

    m.total_leads = row.total or 0
    m.leads_today = row.today or 0
    m.leads_7d = row.d7 or 0
    m.leads_30d = row.total  # 30d = all for now
    m.hot_leads = row.hot or 0
    m.warm_leads = row.warm or 0
    m.cold_leads = row.cold or 0
    m.won_leads = row.won or 0
    m.lost_leads = row.lost or 0
    m.active_leads = row.active or 0

    # Window-filtered 30d count
    stmt_30d = (
        select(func.count())
        .where(
            LeadModel.tenant_id == tenant_id,
            LeadModel.created_at >= (datetime.now(timezone.utc) - timedelta(days=30)),
        )
    )
    result_30d = await session.execute(stmt_30d)
    m.leads_30d = result_30d.scalar() or 0

    if m.total_leads > 0:
        m.conversion_rate = round(m.won_leads / m.total_leads * 100, 1)

    return m


async def _build_operator_metrics(
    session: Any,
    repo: Any,
    tenant_id: int,
) -> OperatorMetrics:
    """Aggregate operator/assignment metrics."""
    from sqlalchemy import select, func
    from infrastructure.database.models.lead import LeadModel

    m = OperatorMetrics()

    stmt = (
        select(
            func.count().filter(
                LeadModel.assigned_manager_id.isnot(None),
            ).label("assigned"),
            func.count().filter(
                LeadModel.assigned_manager_id.is_(None),
            ).label("unassigned"),
            func.count().filter(
                LeadModel.operator_attention.is_(True),
            ).label("attention"),
        )
        .where(
            LeadModel.tenant_id == tenant_id,
            LeadModel.lead_status.notin_(["deal", "lost"])
            | LeadModel.lead_status.is_(None),
        )
    )

    result = await session.execute(stmt)
    row = result.one()
    m.assigned_leads = row.assigned or 0
    m.unassigned_leads = row.unassigned or 0
    m.attention_queue = row.attention or 0

    return m


async def _build_followup_metrics(
    session: Any,
    tenant_id: int,
    window_start: datetime,
) -> FollowUpMetrics:
    """Aggregate follow-up metrics from leads table."""
    from sqlalchemy import select, func
    from infrastructure.database.models.lead import LeadModel

    m = FollowUpMetrics()

    stmt = (
        select(
            func.count().filter(
                LeadModel.next_follow_up_at.isnot(None),
            ).label("scheduled"),
            func.count().filter(
                LeadModel.user_followup_stage > 0,
            ).label("in_followup"),
            func.count().filter(
                LeadModel.user_followup_closed.is_(True),
            ).label("closed"),
            func.avg(LeadModel.follow_up_count).label("avg_count"),
        )
        .where(LeadModel.tenant_id == tenant_id)
    )

    result = await session.execute(stmt)
    row = result.one()
    m.followups_scheduled = row.scheduled or 0
    m.followups_reengaged = row.in_followup or 0
    m.followups_closed = row.closed or 0
    m.avg_followup_count = round(float(row.avg_count or 0), 1)

    return m


async def _build_ai_metrics(
    tenant_id: int,
    window_days: int,
    today_start: datetime,
) -> AIMetrics:
    """Read AI usage from Redis per-tenant quota keys + global stats."""
    m = AIMetrics()

    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        redis = get_redis()
        today_str = today_start.strftime("%Y-%m-%d")

        # Per-tenant daily AI quota (this IS tenant-scoped)
        today_val = await redis.get(CacheKeys.ai_daily_quota(tenant_id, date_str=today_str))
        m.ai_messages_today = int(today_val) if today_val else 0

        # Sum over last N days for the window
        total_7d = 0
        for i in range(min(window_days, 7)):
            d = (today_start - timedelta(days=i)).strftime("%Y-%m-%d")
            val = await redis.get(CacheKeys.ai_daily_quota(tenant_id, date_str=d))
            total_7d += int(val) if val else 0
        m.ai_messages_7d = total_7d

        # Global cache stats (not tenant-scoped, but useful)
        hit_val = await redis.get(CacheKeys.ai_stats_field(today_str, "cache_hit"))
        miss_val = await redis.get(CacheKeys.ai_stats_field(today_str, "cache_miss"))
        m.cache_hit_count = int(hit_val) if hit_val else 0
        m.cache_miss_count = int(miss_val) if miss_val else 0
        total_cache = m.cache_hit_count + m.cache_miss_count
        if total_cache > 0:
            m.cache_hit_rate = round(m.cache_hit_count / total_cache * 100, 1)

    except Exception:
        log.warning("ai_metrics_redis_failed", tenant_id=tenant_id)

    return m


# ── Cache layer ──────────────────────────────────────────────────────────────


async def _get_cached(tenant_id: int, window_days: int) -> OwnerAnalytics | None:
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        raw = await get_redis().get(CacheKeys.owner_analytics(tenant_id, window_days))
        if not raw:
            return None
        data = json.loads(raw)
        return _dict_to_analytics(data)
    except Exception:
        return None


async def _set_cached(tenant_id: int, window_days: int, result: OwnerAnalytics) -> None:
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        data = _analytics_to_dict(result)
        await get_redis().set(
            CacheKeys.owner_analytics(tenant_id, window_days),
            json.dumps(data),
            ttl=CacheTTL.OWNER_ANALYTICS,
        )
    except Exception:
        pass


def _analytics_to_dict(a: OwnerAnalytics) -> dict:
    return {
        "window_days": a.window_days,
        "funnel": {
            "leads_today": a.funnel.leads_today,
            "leads_7d": a.funnel.leads_7d,
            "leads_30d": a.funnel.leads_30d,
            "hot_leads": a.funnel.hot_leads,
            "warm_leads": a.funnel.warm_leads,
            "cold_leads": a.funnel.cold_leads,
            "total_leads": a.funnel.total_leads,
            "won_leads": a.funnel.won_leads,
            "lost_leads": a.funnel.lost_leads,
            "active_leads": a.funnel.active_leads,
            "conversion_rate": a.funnel.conversion_rate,
        },
        "operators": {
            "assigned_leads": a.operators.assigned_leads,
            "unassigned_leads": a.operators.unassigned_leads,
            "attention_queue": a.operators.attention_queue,
            "operators_count": a.operators.operators_count,
        },
        "ai": {
            "ai_messages_today": a.ai.ai_messages_today,
            "ai_messages_7d": a.ai.ai_messages_7d,
            "cache_hit_count": a.ai.cache_hit_count,
            "cache_miss_count": a.ai.cache_miss_count,
            "cache_hit_rate": a.ai.cache_hit_rate,
        },
        "followups": {
            "followups_scheduled": a.followups.followups_scheduled,
            "followups_reengaged": a.followups.followups_reengaged,
            "followups_closed": a.followups.followups_closed,
            "avg_followup_count": a.followups.avg_followup_count,
        },
    }


def _dict_to_analytics(d: dict) -> OwnerAnalytics:
    f = d.get("funnel", {})
    o = d.get("operators", {})
    ai = d.get("ai", {})
    fu = d.get("followups", {})
    return OwnerAnalytics(
        window_days=d.get("window_days", 1),
        funnel=LeadFunnelMetrics(
            leads_today=f.get("leads_today", 0),
            leads_7d=f.get("leads_7d", 0),
            leads_30d=f.get("leads_30d", 0),
            hot_leads=f.get("hot_leads", 0),
            warm_leads=f.get("warm_leads", 0),
            cold_leads=f.get("cold_leads", 0),
            total_leads=f.get("total_leads", 0),
            won_leads=f.get("won_leads", 0),
            lost_leads=f.get("lost_leads", 0),
            active_leads=f.get("active_leads", 0),
            conversion_rate=f.get("conversion_rate", 0.0),
        ),
        operators=OperatorMetrics(
            assigned_leads=o.get("assigned_leads", 0),
            unassigned_leads=o.get("unassigned_leads", 0),
            attention_queue=o.get("attention_queue", 0),
            operators_count=o.get("operators_count", 0),
        ),
        ai=AIMetrics(
            ai_messages_today=ai.get("ai_messages_today", 0),
            ai_messages_7d=ai.get("ai_messages_7d", 0),
            cache_hit_count=ai.get("cache_hit_count", 0),
            cache_miss_count=ai.get("cache_miss_count", 0),
            cache_hit_rate=ai.get("cache_hit_rate", 0.0),
        ),
        followups=FollowUpMetrics(
            followups_scheduled=fu.get("followups_scheduled", 0),
            followups_reengaged=fu.get("followups_reengaged", 0),
            followups_closed=fu.get("followups_closed", 0),
            avg_followup_count=fu.get("avg_followup_count", 0.0),
        ),
    )


# ── Telegram formatter ───────────────────────────────────────────────────────


def format_analytics_summary(a: OwnerAnalytics) -> str:
    """Format analytics as a compact Telegram message."""
    window_label = {1: "Bugun", 7: "7 kun", 30: "30 kun"}.get(
        a.window_days, f"{a.window_days} kun",
    )

    f = a.funnel
    o = a.operators
    ai = a.ai
    fu = a.followups

    lines = [
        f"📊 Analitika — {window_label}",
        "",
        "📈 Lead funnel",
        f"  Bugun: {f.leads_today} | 7k: {f.leads_7d} | 30k: {f.leads_30d}",
        f"  🔥 Hot: {f.hot_leads} | 🌡 Warm: {f.warm_leads} | ❄️ Cold: {f.cold_leads}",
        f"  Jami: {f.total_leads} | Faol: {f.active_leads}",
        f"  Yutilgan: {f.won_leads} | Yo'qotilgan: {f.lost_leads}",
        f"  Konversiya: {f.conversion_rate}%",
        "",
        "🤖 AI ishlashi",
        f"  Xabarlar bugun: {ai.ai_messages_today}",
        f"  Xabarlar {window_label}: {ai.ai_messages_7d}",
        f"  Kesh: {ai.cache_hit_count} hit / {ai.cache_miss_count} miss ({ai.cache_hit_rate}%)",
        "",
        "👔 Operator navbat",
        f"  Tayinlangan: {o.assigned_leads} | Tayinlanmagan: {o.unassigned_leads}",
        f"  ⚠️ Diqqat kerak: {o.attention_queue}",
        f"  Operatorlar: {o.operators_count}",
        "",
        "🔄 Follow-up",
        f"  Rejada: {fu.followups_scheduled} | Javob bergan: {fu.followups_reengaged}",
        f"  Yakunlangan: {fu.followups_closed}",
        f"  O'rtacha: {fu.avg_followup_count} follow-up/lid",
    ]

    return "\n".join(lines)


def format_funnel_detail(a: OwnerAnalytics) -> str:
    """Detailed lead funnel breakdown."""
    f = a.funnel
    lines = [
        "📈 Lead funnel batafsil",
        "",
        f"Bugun yangi: {f.leads_today}",
        f"7 kunda: {f.leads_7d}",
        f"30 kunda: {f.leads_30d}",
        "",
        "Harorat taqsimoti:",
        f"  🔥 Hot: {f.hot_leads}",
        f"  🌡 Warm: {f.warm_leads}",
        f"  ❄️ Cold: {f.cold_leads}",
        "",
        f"Jami lidlar: {f.total_leads}",
        f"Faol: {f.active_leads}",
        f"Yutilgan (deal): {f.won_leads}",
        f"Yo'qotilgan (lost): {f.lost_leads}",
        f"Konversiya: {f.conversion_rate}%",
    ]
    return "\n".join(lines)


def format_operator_detail(a: OwnerAnalytics) -> str:
    """Detailed operator queue breakdown."""
    o = a.operators
    lines = [
        "👔 Operator navbat batafsil",
        "",
        f"Operatorlar soni: {o.operators_count}",
        f"Tayinlangan lidlar: {o.assigned_leads}",
        f"Tayinlanmagan: {o.unassigned_leads}",
        f"⚠️ Diqqat kerak: {o.attention_queue}",
    ]
    if o.operators_count > 0 and o.assigned_leads > 0:
        avg = round(o.assigned_leads / o.operators_count, 1)
        lines.append(f"O'rtacha: {avg} lid/operator")
    return "\n".join(lines)


def format_followup_detail(a: OwnerAnalytics) -> str:
    """Detailed follow-up breakdown."""
    fu = a.followups
    lines = [
        "🔄 Follow-up batafsil",
        "",
        f"Rejada (kutilmoqda): {fu.followups_scheduled}",
        f"Re-engagement boshlangan: {fu.followups_reengaged}",
        f"Yakunlangan: {fu.followups_closed}",
        f"O'rtacha follow-up soni: {fu.avg_followup_count}",
    ]
    return "\n".join(lines)
