"""
core.services.sales_analytics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Summarises sales performance, lead quality, objections, funnel movement,
and action effectiveness from a list of lead signal dicts.

Pure deterministic function — no I/O, fully testable.

Usage::

    from core.services.sales_analytics_service import build_sales_analytics

    report = build_sales_analytics(leads_data)
    # report.total_leads == 124
    # report.conversion_rate == 0.145
    # report.top_sources == [{"source": "group", "leads": 62, "won": 11}]
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SalesAnalytics:
    """Comprehensive sales analytics report."""

    # ── Total summary ─────────────────────────────────────────────────
    total_leads: int
    won_leads: int
    lost_leads: int
    active_leads: int
    conversion_rate: float
    """Won / total (0.0–1.0)."""

    # ── Source performance ────────────────────────────────────────────
    top_sources: list[dict]
    """[{"source": "group", "leads": 62, "won": 11, "lost": 20, "rate": 0.18}]"""

    # ── Buyer type conversion ─────────────────────────────────────────
    buyer_type_stats: list[dict]
    """[{"type": "fast_buyer", "count": 15, "won": 5, "rate": 0.33}]"""

    best_buyer_type: dict | None
    """{"type": "fast_buyer", "close_rate": 0.34} or None."""

    # ── Objection breakdown ───────────────────────────────────────────
    top_objections: list[dict]
    """[{"type": "expensive", "count": 29}]"""

    objection_severity_stats: dict
    """{"low": 10, "medium": 5, "high": 2}"""

    objection_lost_correlation: list[dict]
    """[{"type": "expensive", "total": 29, "lost": 12, "lost_rate": 0.41}]"""

    # ── Negotiation tactic effectiveness ─────────────────────────────
    tactic_stats: list[dict]
    """[{"tactic": "value_reframe", "count": 8, "won": 3, "rate": 0.375}]"""

    best_tactic: dict | None
    """{"tactic": "value_reframe", "won_rate": 0.38} or None."""

    # ── Funnel stages ─────────────────────────────────────────────────
    stage_counts: list[dict]
    """[{"stage": "NEW", "count": 30}, ...] in pipeline order."""

    largest_dropoff_stage: str | None
    """Stage where the biggest relative drop happens."""

    # ── Follow-up performance ─────────────────────────────────────────
    followup_stats: dict
    """{
        "avg_followups_won": 2.1,
        "avg_followups_lost": 3.4,
        "avg_followups_all": 2.8,
        "with_followup_pct": 0.65,
    }"""

    best_followup_type: dict | None
    """{"type": "measurement_push", "count": 12, "won": 4, "rate": 0.33}"""

    followup_type_stats: list[dict]
    """[{"type": "measurement_push", "count": 12, "won": 4, "rate": 0.33}]"""

    # ── Score distribution ────────────────────────────────────────────
    score_distribution: dict
    """{"hot": 12, "warm": 35, "cold": 77}"""

    avg_score: float

    # ── Revenue summary ───────────────────────────────────────────────
    total_estimated_revenue: int
    """Sum of predicted_revenue_best across all leads with revenue data."""

    avg_revenue_per_lead: int

    # ── Conversation health ────────────────────────────────────────────
    avg_health_score: float
    """Average conversation health score across leads with data."""

    health_distribution: dict
    """{"healthy": N, "at_risk": N, "critical": N}"""

    top_signals: list[dict]
    """[{"signal": "price_resistance", "count": 15}] — most common signals."""

    cooling_count: int
    """Number of leads currently cooling down."""

    # ── Autopilot metrics ─────────────────────────────────────────────
    autopilot_action_distribution: list[dict]
    """[{"action": "schedule_measurement", "count": 8}]"""

    opportunity_count: int
    """Leads with high-conversion opportunity detected."""

    at_risk_count: int
    """Leads at risk of being lost."""

    closing_ready_count: int
    """Leads ready for deal closing."""

    # ── Closing readiness metrics ──────────────────────────────────────
    closing_readiness_distribution: dict
    """{"NOT_READY": N, "NEAR_CLOSE": N, "READY_TO_CLOSE": N}"""

    close_opportunity_count: int
    """Leads with READY_TO_CLOSE tier."""

    close_loss_risk_count: int
    """Leads with close-loss risk detected."""

    closing_tactic_distribution: list[dict]
    """[{"tactic": "measurement_booking", "count": 5}]"""

    # ── Auto-seller metrics ──────────────────────────────────────────
    auto_reply_count: int
    """Leads that received at least one auto-reply."""

    auto_escalation_count: int
    """Leads escalated to manager by auto-seller."""

    auto_reply_confidence_avg: float
    """Average auto-reply decision confidence (0.0–1.0)."""

    # ── Recommendations ───────────────────────────────────────────────
    recommendations: list[str]
    """Actionable recommendations based on the data."""


# ── Pipeline stage order (for funnel analysis) ───────────────────────────────

_STAGE_ORDER = [
    "NEW", "PACKAGE_SELECTED", "CONTACTED",
    "MEASUREMENT", "QUOTE", "DEAL",
    "INSTALLATION", "COMPLETED", "LOST",
]

_STAGE_LABELS: dict[str, str] = {
    "NEW": "Yangi",
    "PACKAGE_SELECTED": "Paket tanlangan",
    "CONTACTED": "Bog'lanilgan",
    "MEASUREMENT": "O'lchov",
    "QUOTE": "Narx berilgan",
    "DEAL": "Kelishilgan",
    "INSTALLATION": "O'rnatish",
    "COMPLETED": "Tugallangan",
    "LOST": "Yo'qotilgan",
}

# Terminal statuses in lead_status field
_WON_STATUSES = frozenset({"deal"})
_LOST_STATUSES = frozenset({"lost"})


# ── Main builder ─────────────────────────────────────────────────────────────


def build_sales_analytics(leads_data: list[dict]) -> SalesAnalytics:
    """Build a complete analytics report from lead signal dicts.

    Each dict in *leads_data* should contain::

        {
            "lead_id": int,
            "source": str,           # LeadSource value
            "current_stage": str,     # PipelineStage value
            "lead_status": str|None,  # hot/warm/cold/deal/lost
            "score": int,
            "phone": str,
            "district": str,
            "room_area": float|None,
            "follow_up_count": int,
            "closing_confidence": float|None,
            "lead_temperature": str|None,
            # Optional enrichment from Redis AI memory:
            "buyer_type": str|None,
            "last_objection": str|None,
            "last_fu_type": str|None,
            "predicted_revenue_best": int|None,
        }

    Pure function — no I/O, fully deterministic.
    """
    total = len(leads_data)
    if total == 0:
        return _empty_analytics()

    # ── Classify leads ────────────────────────────────────────────────
    won = 0
    lost = 0
    active = 0
    for ld in leads_data:
        status = ld.get("lead_status")
        stage = ld.get("current_stage", "")
        if status in _WON_STATUSES or stage in ("DEAL", "COMPLETED"):
            won += 1
        elif status in _LOST_STATUSES or stage == "LOST":
            lost += 1
        else:
            active += 1

    conversion_rate = won / total if total > 0 else 0.0

    # ── Source performance ────────────────────────────────────────────
    top_sources = _compute_source_stats(leads_data)

    # ── Buyer type conversion ─────────────────────────────────────────
    buyer_type_stats = _compute_buyer_type_stats(leads_data)
    best_buyer_type = None
    if buyer_type_stats:
        best = max(buyer_type_stats, key=lambda x: x["rate"])
        if best["rate"] > 0:
            best_buyer_type = {"type": best["type"], "close_rate": best["rate"]}

    # ── Objection breakdown ───────────────────────────────────────────
    top_objections = _compute_objection_stats(leads_data)
    objection_severity_stats = _compute_severity_stats(leads_data)
    objection_lost_correlation = _compute_objection_lost_correlation(leads_data)

    # ── Negotiation tactic effectiveness ──────────────────────────────
    tactic_stats = _compute_tactic_stats(leads_data)
    best_tactic = None
    if tactic_stats:
        best = max(tactic_stats, key=lambda x: x["rate"])
        if best["rate"] > 0:
            best_tactic = {"tactic": best["tactic"], "won_rate": best["rate"]}

    # ── Funnel stages ─────────────────────────────────────────────────
    stage_counts, largest_dropoff = _compute_funnel_stats(leads_data)

    # ── Follow-up performance ─────────────────────────────────────────
    followup_stats = _compute_followup_stats(leads_data)
    fu_type_stats = _compute_followup_type_stats(leads_data)
    best_fu = None
    if fu_type_stats:
        best = max(fu_type_stats, key=lambda x: x["rate"])
        if best["rate"] > 0:
            best_fu = best

    # ── Score distribution ────────────────────────────────────────────
    scores = [ld.get("score", 0) for ld in leads_data]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    hot_count = sum(1 for s in scores if s >= 60)
    warm_count = sum(1 for s in scores if 30 <= s < 60)
    cold_count = sum(1 for s in scores if s < 30)

    # ── Revenue summary ───────────────────────────────────────────────
    revenues = [
        ld["predicted_revenue_best"]
        for ld in leads_data
        if ld.get("predicted_revenue_best")
    ]
    total_revenue = sum(revenues) if revenues else 0
    avg_revenue = total_revenue // len(revenues) if revenues else 0

    # ── Conversation health ───────────────────────────────────────────
    conv_health = _compute_conversation_health_stats(leads_data)

    # ── Autopilot metrics ─────────────────────────────────────────────
    autopilot = _compute_autopilot_stats(leads_data)

    # ── Closing readiness metrics ──────────────────────────────────────
    closing = _compute_closing_stats(leads_data)

    # ── Auto-seller metrics ──────────────────────────────────────────
    auto_sales = _compute_auto_sales_stats(leads_data)

    # ── Recommendations ───────────────────────────────────────────────
    recommendations = _build_recommendations(
        conversion_rate=conversion_rate,
        top_objections=top_objections,
        largest_dropoff=largest_dropoff,
        followup_stats=followup_stats,
        best_buyer_type=best_buyer_type,
        active=active,
        won=won,
        lost=lost,
        avg_score=avg_score,
        objection_severity_stats=objection_severity_stats,
        objection_lost_correlation=objection_lost_correlation,
        best_tactic=best_tactic,
        conv_health=conv_health,
    )

    return SalesAnalytics(
        total_leads=total,
        won_leads=won,
        lost_leads=lost,
        active_leads=active,
        conversion_rate=round(conversion_rate, 3),
        top_sources=top_sources,
        buyer_type_stats=buyer_type_stats,
        best_buyer_type=best_buyer_type,
        top_objections=top_objections,
        objection_severity_stats=objection_severity_stats,
        objection_lost_correlation=objection_lost_correlation,
        tactic_stats=tactic_stats,
        best_tactic=best_tactic,
        stage_counts=stage_counts,
        largest_dropoff_stage=largest_dropoff,
        followup_stats=followup_stats,
        best_followup_type=best_fu,
        followup_type_stats=fu_type_stats,
        score_distribution={"hot": hot_count, "warm": warm_count, "cold": cold_count},
        avg_score=round(avg_score, 1),
        total_estimated_revenue=total_revenue,
        avg_revenue_per_lead=avg_revenue,
        avg_health_score=conv_health["avg_health"],
        health_distribution=conv_health["distribution"],
        top_signals=conv_health["top_signals"],
        cooling_count=conv_health["cooling_count"],
        autopilot_action_distribution=autopilot["action_distribution"],
        opportunity_count=autopilot["opportunity_count"],
        at_risk_count=autopilot["at_risk_count"],
        closing_ready_count=autopilot["closing_ready_count"],
        closing_readiness_distribution=closing["readiness_distribution"],
        close_opportunity_count=closing["opportunity_count"],
        close_loss_risk_count=closing["loss_risk_count"],
        closing_tactic_distribution=closing["tactic_distribution"],
        auto_reply_count=auto_sales["auto_reply_count"],
        auto_escalation_count=auto_sales["auto_escalation_count"],
        auto_reply_confidence_avg=auto_sales["auto_reply_confidence_avg"],
        recommendations=recommendations,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _empty_analytics() -> SalesAnalytics:
    """Return an empty analytics report."""
    return SalesAnalytics(
        total_leads=0, won_leads=0, lost_leads=0, active_leads=0,
        conversion_rate=0.0, top_sources=[], buyer_type_stats=[],
        best_buyer_type=None, top_objections=[],
        objection_severity_stats={"low": 0, "medium": 0, "high": 0},
        objection_lost_correlation=[], tactic_stats=[], best_tactic=None,
        stage_counts=[], largest_dropoff_stage=None, followup_stats={
            "avg_followups_won": 0, "avg_followups_lost": 0,
            "avg_followups_all": 0, "with_followup_pct": 0,
        },
        best_followup_type=None, followup_type_stats=[],
        score_distribution={"hot": 0, "warm": 0, "cold": 0},
        avg_score=0.0, total_estimated_revenue=0,
        avg_revenue_per_lead=0,
        avg_health_score=0.0,
        health_distribution={"healthy": 0, "at_risk": 0, "critical": 0},
        top_signals=[], cooling_count=0,
        autopilot_action_distribution=[], opportunity_count=0,
        at_risk_count=0, closing_ready_count=0,
        closing_readiness_distribution={"NOT_READY": 0, "NEAR_CLOSE": 0, "READY_TO_CLOSE": 0},
        close_opportunity_count=0, close_loss_risk_count=0,
        closing_tactic_distribution=[],
        auto_reply_count=0, auto_escalation_count=0,
        auto_reply_confidence_avg=0.0,
        recommendations=[],
    )


def _is_won(ld: dict) -> bool:
    status = ld.get("lead_status")
    stage = ld.get("current_stage", "")
    return status in _WON_STATUSES or stage in ("DEAL", "COMPLETED")


def _is_lost(ld: dict) -> bool:
    status = ld.get("lead_status")
    stage = ld.get("current_stage", "")
    return status in _LOST_STATUSES or stage == "LOST"


def _compute_source_stats(leads_data: list[dict]) -> list[dict]:
    """Group leads by source, compute won/lost/rate."""
    by_source: dict[str, dict] = {}
    for ld in leads_data:
        src = ld.get("source", "unknown")
        if src not in by_source:
            by_source[src] = {"source": src, "leads": 0, "won": 0, "lost": 0}
        by_source[src]["leads"] += 1
        if _is_won(ld):
            by_source[src]["won"] += 1
        elif _is_lost(ld):
            by_source[src]["lost"] += 1

    result = list(by_source.values())
    for r in result:
        r["rate"] = round(r["won"] / r["leads"], 3) if r["leads"] > 0 else 0.0
    result.sort(key=lambda x: x["leads"], reverse=True)
    return result


def _compute_buyer_type_stats(leads_data: list[dict]) -> list[dict]:
    """Group leads by buyer_type (from Redis), compute conversion."""
    by_type: dict[str, dict] = {}
    for ld in leads_data:
        bt = ld.get("buyer_type")
        if not bt:
            continue
        if bt not in by_type:
            by_type[bt] = {"type": bt, "count": 0, "won": 0}
        by_type[bt]["count"] += 1
        if _is_won(ld):
            by_type[bt]["won"] += 1

    result = list(by_type.values())
    for r in result:
        r["rate"] = round(r["won"] / r["count"], 3) if r["count"] > 0 else 0.0
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def _compute_objection_stats(leads_data: list[dict]) -> list[dict]:
    """Count objections from Redis AI memory."""
    counter: Counter = Counter()
    for ld in leads_data:
        obj = ld.get("last_objection")
        if obj:
            counter[obj] += 1

    return [
        {"type": t, "count": c}
        for t, c in counter.most_common(5)
    ]


def _compute_funnel_stats(
    leads_data: list[dict],
) -> tuple[list[dict], str | None]:
    """Count leads per pipeline stage, find largest dropoff."""
    counter: Counter = Counter()
    for ld in leads_data:
        stage = ld.get("current_stage", "NEW")
        counter[stage] += 1

    # Build ordered list (only stages with leads)
    stage_counts = []
    for stage in _STAGE_ORDER:
        count = counter.get(stage, 0)
        if count > 0 or stage in ("NEW", "CONTACTED", "MEASUREMENT", "DEAL", "LOST"):
            stage_counts.append({"stage": stage, "count": count})

    # Find largest relative dropoff in the funnel (exclude LOST)
    funnel_stages = [s for s in _STAGE_ORDER if s != "LOST"]
    largest_dropoff: str | None = None
    largest_drop_pct = 0.0

    for i in range(len(funnel_stages) - 1):
        current = counter.get(funnel_stages[i], 0)
        next_stage = counter.get(funnel_stages[i + 1], 0)
        if current > 0:
            drop_pct = (current - next_stage) / current
            if drop_pct > largest_drop_pct and current >= 3:
                largest_drop_pct = drop_pct
                largest_dropoff = funnel_stages[i]

    return stage_counts, largest_dropoff


def _compute_severity_stats(leads_data: list[dict]) -> dict:
    """Count objections by severity level."""
    counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
    for ld in leads_data:
        sev = ld.get("last_objection_severity")
        if sev and sev in counts:
            counts[sev] += 1
    return counts


def _compute_objection_lost_correlation(leads_data: list[dict]) -> list[dict]:
    """Compute lost rate per objection type."""
    by_type: dict[str, dict] = {}
    for ld in leads_data:
        obj = ld.get("last_objection")
        if not obj:
            continue
        if obj not in by_type:
            by_type[obj] = {"type": obj, "total": 0, "lost": 0}
        by_type[obj]["total"] += 1
        if _is_lost(ld):
            by_type[obj]["lost"] += 1

    result = list(by_type.values())
    for r in result:
        r["lost_rate"] = round(r["lost"] / r["total"], 3) if r["total"] > 0 else 0.0
    result.sort(key=lambda x: x["lost_rate"], reverse=True)
    return result


def _compute_tactic_stats(leads_data: list[dict]) -> list[dict]:
    """Group leads by last negotiation tactic, compute won rate."""
    by_tactic: dict[str, dict] = {}
    for ld in leads_data:
        tactic = ld.get("last_negotiation_tactic")
        if not tactic or tactic == "none":
            continue
        if tactic not in by_tactic:
            by_tactic[tactic] = {"tactic": tactic, "count": 0, "won": 0}
        by_tactic[tactic]["count"] += 1
        if _is_won(ld):
            by_tactic[tactic]["won"] += 1

    result = list(by_tactic.values())
    for r in result:
        r["rate"] = round(r["won"] / r["count"], 3) if r["count"] > 0 else 0.0
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def _compute_followup_stats(leads_data: list[dict]) -> dict:
    """Compute follow-up effectiveness stats."""
    won_fus = [
        ld.get("follow_up_count", 0)
        for ld in leads_data
        if _is_won(ld)
    ]
    lost_fus = [
        ld.get("follow_up_count", 0)
        for ld in leads_data
        if _is_lost(ld)
    ]
    all_fus = [ld.get("follow_up_count", 0) for ld in leads_data]
    with_fu = sum(1 for f in all_fus if f > 0)

    return {
        "avg_followups_won": round(sum(won_fus) / len(won_fus), 1) if won_fus else 0,
        "avg_followups_lost": round(sum(lost_fus) / len(lost_fus), 1) if lost_fus else 0,
        "avg_followups_all": round(sum(all_fus) / len(all_fus), 1) if all_fus else 0,
        "with_followup_pct": round(with_fu / len(all_fus), 2) if all_fus else 0,
    }


def _compute_followup_type_stats(leads_data: list[dict]) -> list[dict]:
    """Group leads by follow-up type (from Redis), compute won rate."""
    by_type: dict[str, dict] = {}
    for ld in leads_data:
        fu_type = ld.get("last_fu_type")
        if not fu_type or fu_type == "none":
            continue
        if fu_type not in by_type:
            by_type[fu_type] = {"type": fu_type, "count": 0, "won": 0}
        by_type[fu_type]["count"] += 1
        if _is_won(ld):
            by_type[fu_type]["won"] += 1

    result = list(by_type.values())
    for r in result:
        r["rate"] = round(r["won"] / r["count"], 3) if r["count"] > 0 else 0.0
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def _compute_conversation_health_stats(leads_data: list[dict]) -> dict:
    """Compute conversation health metrics from enriched lead dicts.

    Expects optional keys: ``conv_health_score``, ``conv_signals``,
    ``conv_risk_level``, ``conv_cooling``.
    """
    health_scores: list[int] = []
    signal_counter: Counter = Counter()
    cooling = 0
    healthy = 0
    at_risk = 0
    critical = 0

    for ld in leads_data:
        hs = ld.get("conv_health_score")
        if hs is None:
            continue
        health_scores.append(hs)

        # Classify into buckets
        if hs >= 70:
            healthy += 1
        elif hs >= 40:
            at_risk += 1
        else:
            critical += 1

        # Count signals
        for sig in (ld.get("conv_signals") or []):
            signal_counter[sig] += 1

        if ld.get("conv_cooling"):
            cooling += 1

    avg_health = round(sum(health_scores) / len(health_scores), 1) if health_scores else 0.0
    top_signals = [
        {"signal": sig, "count": cnt}
        for sig, cnt in signal_counter.most_common(5)
    ]

    return {
        "avg_health": avg_health,
        "distribution": {"healthy": healthy, "at_risk": at_risk, "critical": critical},
        "top_signals": top_signals,
        "cooling_count": cooling,
    }


def _compute_autopilot_stats(leads_data: list[dict]) -> dict:
    """Compute autopilot metrics from enriched lead dicts.

    Expects optional keys: ``nba_action``, ``opportunity_detected``,
    ``at_risk_detected``, ``closing_ready``.
    """
    action_counter: Counter = Counter()
    opportunity_count = 0
    at_risk_count = 0
    closing_ready_count = 0

    for ld in leads_data:
        action = ld.get("nba_action")
        if action:
            action_counter[action] += 1
        if ld.get("opportunity_detected"):
            opportunity_count += 1
        if ld.get("at_risk_detected"):
            at_risk_count += 1
        if ld.get("closing_ready"):
            closing_ready_count += 1

    return {
        "action_distribution": [
            {"action": a, "count": c}
            for a, c in action_counter.most_common(6)
        ],
        "opportunity_count": opportunity_count,
        "at_risk_count": at_risk_count,
        "closing_ready_count": closing_ready_count,
    }


def _compute_closing_stats(leads_data: list[dict]) -> dict:
    """Compute closing readiness metrics from enriched lead dicts.

    Expects optional keys: ``closing_readiness_tier``, ``closing_loss_risk``,
    ``closing_tactic``.
    """
    tier_counter: Counter = Counter()
    tactic_counter: Counter = Counter()
    loss_risk_count = 0

    for ld in leads_data:
        tier = ld.get("closing_readiness_tier")
        if tier:
            tier_counter[tier] += 1
        if ld.get("closing_loss_risk"):
            loss_risk_count += 1
        tactic = ld.get("closing_tactic")
        if tactic:
            tactic_counter[tactic] += 1

    return {
        "readiness_distribution": {
            "NOT_READY": tier_counter.get("NOT_READY", 0),
            "NEAR_CLOSE": tier_counter.get("NEAR_CLOSE", 0),
            "READY_TO_CLOSE": tier_counter.get("READY_TO_CLOSE", 0),
        },
        "opportunity_count": tier_counter.get("READY_TO_CLOSE", 0),
        "loss_risk_count": loss_risk_count,
        "tactic_distribution": [
            {"tactic": t, "count": c}
            for t, c in tactic_counter.most_common(6)
        ],
    }


def _compute_auto_sales_stats(leads_data: list[dict]) -> dict:
    """Compute auto-seller metrics from enriched lead dicts.

    Expects optional keys: ``auto_reply_used``, ``auto_escalated``,
    ``auto_reply_confidence``.
    """
    auto_reply_count = 0
    auto_escalation_count = 0
    confidences: list[float] = []

    for ld in leads_data:
        if ld.get("auto_reply_used"):
            auto_reply_count += 1
        if ld.get("auto_escalated"):
            auto_escalation_count += 1
        conf = ld.get("auto_reply_confidence")
        if conf is not None:
            confidences.append(conf)

    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    return {
        "auto_reply_count": auto_reply_count,
        "auto_escalation_count": auto_escalation_count,
        "auto_reply_confidence_avg": avg_conf,
    }


def _build_recommendations(
    *,
    conversion_rate: float,
    top_objections: list[dict],
    largest_dropoff: str | None,
    followup_stats: dict,
    best_buyer_type: dict | None,
    active: int,
    won: int,
    lost: int,
    avg_score: float,
    objection_severity_stats: dict | None = None,
    objection_lost_correlation: list[dict] | None = None,
    best_tactic: dict | None = None,
    conv_health: dict | None = None,
) -> list[str]:
    """Generate actionable recommendations from analytics data."""
    recs: list[str] = []

    # Low conversion rate
    if conversion_rate < 0.15 and (won + lost) >= 5:
        recs.append(
            "Konversiya past (%.0f%%) — closing CTAlarni kuchaytiring"
            % (conversion_rate * 100)
        )

    # Dominant objection
    if top_objections:
        top = top_objections[0]
        if top["count"] >= 5:
            _obj_advice: dict[str, str] = {
                "expensive": "Narx e'tirozlari ko'p — byudjet variantlarini oldin taklif qiling",
                "delay": "Ko'p lid kechiktirmoqda — urgency CTA qo'shing",
                "trust": "Ishonch muammosi bor — referallar va natijalar ko'rsating",
                "compare": "Taqqoslash ko'p — raqobat ustunliklarini ta'kidlang",
                "angry": "Norozilik bor — xizmat sifatini tekshiring",
            }
            advice = _obj_advice.get(
                top["type"],
                f"{top['type']} e'tirozini kamaytirish ustida ishlang",
            )
            recs.append(advice)

    # Funnel dropoff
    if largest_dropoff:
        label = _STAGE_LABELS.get(largest_dropoff, largest_dropoff)
        recs.append(
            f"'{label}' bosqichida eng ko'p yo'qotish — "
            f"bu bosqichda CTA va follow-upni kuchaytiring"
        )

    # Follow-up usage
    fu_pct = followup_stats.get("with_followup_pct", 0)
    if fu_pct < 0.5 and active >= 5:
        recs.append(
            "Lidlarning %.0f%%ida follow-up yo'q — "
            "avtomatik follow-upni kuchaytiring" % (fu_pct * 100)
        )

    # Won leads have fewer follow-ups → good sign
    avg_won = followup_stats.get("avg_followups_won", 0)
    avg_lost = followup_stats.get("avg_followups_lost", 0)
    if avg_won > 0 and avg_lost > avg_won * 2 and avg_lost >= 3:
        recs.append(
            "Yo'qotilgan lidlarda ko'p follow-up (%.1f) — "
            "erta bosqichda sifat filtrlashni kuchaytiring" % avg_lost
        )

    # Low average score
    if avg_score < 20 and active >= 10:
        recs.append("O'rtacha ball past (%.0f) — lid sifatini yaxshilang" % avg_score)

    # Best buyer type insight
    if best_buyer_type and best_buyer_type["close_rate"] >= 0.2:
        recs.append(
            "%s tipi eng yaxshi konversiya (%.0f%%) — "
            "shu turdagi lidlarga ustunlik bering"
            % (best_buyer_type["type"], best_buyer_type["close_rate"] * 100)
        )

    # High lost ratio
    total = won + lost + active
    if total > 0 and lost / total > 0.4:
        recs.append(
            "Yo'qotish darajasi yuqori (%.0f%%) — sabab tahlilini o'tkazing"
            % (lost / total * 100)
        )

    # High severity objections need attention
    if objection_severity_stats:
        high = objection_severity_stats.get("high", 0)
        if high >= 3:
            recs.append(
                "%d ta yuqori darajali e'tiroz — menejer jalb qilishni ko'paytiring" % high
            )

    # Worst objection-to-lost correlation
    if objection_lost_correlation:
        worst = objection_lost_correlation[0]
        if worst["total"] >= 3 and worst["lost_rate"] >= 0.5:
            _type_names = {
                "expensive": "Narx", "trust": "Ishonch", "delay": "Kechiktirish",
                "compare": "Taqqoslash", "angry": "Norozilik",
            }
            name = _type_names.get(worst["type"], worst["type"])
            recs.append(
                "%s e'tirozi eng ko'p yo'qotishga olib kelmoqda (%.0f%%) — "
                "bu turdagi javoblarni kuchaytiring" % (name, worst["lost_rate"] * 100)
            )

    # Best tactic insight
    if best_tactic and best_tactic["won_rate"] >= 0.2:
        from core.services.negotiation_engine_service import TACTIC_LABELS
        tactic_label = TACTIC_LABELS.get(best_tactic["tactic"], best_tactic["tactic"])
        recs.append(
            "'%s' taktikasi eng samarali (%.0f%%) — "
            "ko'proq foydalaning" % (tactic_label, best_tactic["won_rate"] * 100)
        )

    # Conversation health warnings
    if conv_health:
        crit = conv_health.get("distribution", {}).get("critical", 0)
        cooling = conv_health.get("cooling_count", 0)
        if crit >= 3:
            recs.append(
                "%d ta lid kritik holatda — darhol aralashish kerak" % crit
            )
        if cooling >= 5:
            recs.append(
                "%d ta lid sovumoqda — follow-up va reactivation boshlang" % cooling
            )

    return recs[:5]  # Cap at 5 recommendations
