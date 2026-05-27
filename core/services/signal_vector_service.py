"""
core.services.signal_vector_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unified Signal Vector — single normalised representation of all CRM signals.

Eliminates double-counting across scoring engines by:
1. Decomposing ``lead_score`` to extract *pure* behavioural engagement
   (stripping phone/area/district/confidence bonuses already embedded).
2. Packaging demographic/contact signals into ``contact_quality`` (0-1).
3. Normalising every dimension to 0.0–1.0 so engines use comparable scales.

Producers (``compute_lead_score``, ``analyze_conversation``) stay unchanged.
Consumers (deal_probability, closing_readiness, deal_radar, next_best_action)
accept an optional ``signal_vector`` kwarg and use normalised scores.

Usage::

    from core.services.signal_vector_service import build_signal_vector

    sv = build_signal_vector(
        lead_score=72, health_score=65,
        phone_captured=True, has_area=True, area_m2=22.0,
        has_district=True, closing_confidence=0.7,
    )
    dp = evaluate_deal_probability(signal_vector=sv)
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace as dc_replace

# ── Stage → normalised progress mapping ─────────────────────────────────────

_STAGE_PROGRESS: dict[str, float] = {
    "NEW": 0.10,
    "PACKAGE_SELECTED": 0.20,
    "CONTACTED": 0.30,
    "MEASUREMENT": 0.50,
    "QUOTE": 0.60,
    "DEAL": 0.80,
    "INSTALLATION": 0.90,
    "COMPLETED": 1.00,
    "LOST": 0.00,
}

# ── Intent → strength mapping ───────────────────────────────────────────────

_INTENT_STRENGTH: dict[str, float] = {
    "measurement": 0.9,
    "price": 0.8,
    "package": 0.6,
    "catalog": 0.5,
    "general": 0.3,
}


# ── SignalVector dataclass ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SignalVector:
    """Unified, normalised signal container for all CRM intelligence engines.

    **Normalised scores** (0.0–1.0) are computed once by
    :func:`build_signal_vector` from raw CRM data.  Engines consume these
    without re-deriving, eliminating double-counting.

    **Boolean flags** are preserved for threshold/rule-based engines that
    need simple yes/no checks.

    **Raw context** values are carried through for non-scoring logic
    (deal value calculation, tactic selection, recommendation text).
    """

    # ── 12 normalised scores (0.0 – 1.0) ─────────────────────────────
    engagement_score: float = 0.0
    """Pure behavioural engagement (lead_score minus embedded signal bonuses)."""

    health_score: float = 0.5
    """Conversation health normalised (raw / 100)."""

    confidence_score: float = 0.0
    """AI closing confidence, clamped 0–1."""

    contact_quality: float = 0.0
    """phone(0.5) + area(0.3) + district(0.2)."""

    temperature_score: float = 0.0
    """hot=1.0, warm=0.5, cold=0.0."""

    recency_score: float = 0.0
    """Inverse of inactivity: 1.0 if ≤30 min → 0.0 if >24 h."""

    pipeline_progress: float = 0.0
    """Stage → 0.0–1.0 (NEW=0.1 … COMPLETED=1.0)."""

    objection_score: float = 0.0
    """+1.0 resolved, 0.0 none, negative by severity."""

    intent_strength: float = 0.0
    """measurement=0.9, price=0.8, package=0.6, catalog=0.5, general=0.3."""

    closing_progress: float = 0.0
    """closing_attempted(0.6) + closing_action(0.4)."""

    followup_pressure: float = 0.0
    """follow_up_count / 5, clamped 0–1.  Higher = more fatigued."""

    revenue_potential: float = 0.0
    """predicted_revenue_best / 20 000 000, clamped 0–1."""

    # ── Boolean flags (threshold rules) ───────────────────────────────
    phone_captured: bool = False
    has_area: bool = False
    has_district: bool = False
    closing_attempted: bool = False
    objection_resolved: bool = False
    negotiation_escalated: bool = False

    # ── Raw context (not for scoring — for recommendations / display) ─
    area_m2: float | None = None
    last_objection: str | None = None
    last_objection_severity: str | None = None
    intent: str | None = None
    lead_temperature: str | None = None
    buyer_type: str | None = None
    current_stage: str | None = None
    design_type: str | None = None
    closing_action: str | None = None
    lead_status: str | None = None
    follow_up_count: int = 0
    follow_up_type: str | None = None
    follow_up_should: bool = True
    minutes_since_last_activity: int = 0
    last_activity_ts: int | None = None
    decision_stage: str | None = None
    engagement_trend: str | None = None
    predicted_revenue_best: int | None = None
    predicted_revenue_max: int | None = None

    # ── Time context ───────────────────────────────────────────────────
    time_of_day_bucket: str = "afternoon"
    """morning | afternoon | evening | night — influences CTA urgency."""

    is_business_hours: bool = True
    """Whether the current time is within configured business hours."""

    # ── Original producer scores (for display / logging) ──────────────
    lead_score_raw: int = 0
    health_score_raw: int = 50
    closing_confidence_raw: float | None = None
    deal_probability_percent: int | None = None


# ── Builder function ────────────────────────────────────────────────────────


def build_signal_vector(
    *,
    lead_score: int = 0,
    health_score: int = 50,
    closing_confidence: float | None = None,
    phone_captured: bool = False,
    has_area: bool = False,
    area_m2: float | None = None,
    has_district: bool = False,
    closing_attempted: bool = False,
    closing_action: str | None = None,
    objection_resolved: bool = False,
    last_objection: str | None = None,
    last_objection_severity: str | None = None,
    intent: str | None = None,
    lead_temperature: str | None = None,
    buyer_type: str | None = None,
    current_stage: str | None = None,
    design_type: str | None = None,
    lead_status: str | None = None,
    follow_up_count: int = 0,
    follow_up_type: str | None = None,
    follow_up_should: bool = True,
    minutes_since_last_activity: int = 0,
    last_activity_ts: int | None = None,
    decision_stage: str | None = None,
    engagement_trend: str | None = None,
    negotiation_escalated: bool = False,
    predicted_revenue_best: int | None = None,
    predicted_revenue_max: int | None = None,
    deal_probability_percent: int | None = None,
) -> SignalVector:
    """Build a normalised SignalVector from raw CRM data.

    All parameters are keyword-only with safe defaults so callers can
    pass only what they have.
    """
    # ── 1. Pure engagement (decompose lead_score) ─────────────────────
    pure = lead_score
    if phone_captured:
        pure -= 10
    if has_area or area_m2 is not None:
        pure -= 5
    if has_district:
        pure -= 3
    if closing_confidence:
        pure -= min(closing_confidence * 8, 8)
    engagement = max(0.0, min(1.0, pure / 100.0))

    # ── 2. Health ─────────────────────────────────────────────────────
    health_norm = max(0.0, min(1.0, health_score / 100.0))

    # ── 3. Confidence ─────────────────────────────────────────────────
    conf = max(0.0, min(1.0, closing_confidence or 0.0))

    # ── 4. Contact quality ────────────────────────────────────────────
    cq = 0.0
    if phone_captured:
        cq += 0.5
    if has_area or area_m2 is not None:
        cq += 0.3
    if has_district:
        cq += 0.2

    # ── 5. Temperature ────────────────────────────────────────────────
    _temp_map = {"hot": 1.0, "warm": 0.5, "cold": 0.0}
    temp_score = _temp_map.get((lead_temperature or "").lower(), 0.0)

    # ── 6. Recency ────────────────────────────────────────────────────
    mins = minutes_since_last_activity
    if mins <= 30:
        recency = 1.0
    elif mins <= 120:
        recency = 0.8
    elif mins <= 360:
        recency = 0.5
    elif mins <= 1440:
        recency = 0.2
    else:
        recency = 0.0

    # ── 7. Pipeline progress ──────────────────────────────────────────
    stage_upper = (current_stage or "NEW").upper()
    pipeline = _STAGE_PROGRESS.get(stage_upper, 0.1)

    # ── 8. Objection score ────────────────────────────────────────────
    if last_objection is None:
        obj_score = 0.0
    elif objection_resolved:
        obj_score = 1.0
    else:
        _sev_map = {"low": -0.3, "medium": -0.6, "high": -1.0}
        obj_score = _sev_map.get(
            (last_objection_severity or "low").lower(),
            -0.3,
        )

    # ── 9. Intent strength ────────────────────────────────────────────
    intent_str = _INTENT_STRENGTH.get((intent or "").lower(), 0.0)

    # ── 10. Closing progress ──────────────────────────────────────────
    closing_prog = 0.0
    if closing_attempted:
        closing_prog += 0.6
    if closing_action:
        closing_prog += 0.4

    # ── 11. Follow-up pressure ────────────────────────────────────────
    fu_pressure = max(0.0, min(1.0, follow_up_count / 5.0))

    # ── 12. Revenue potential ─────────────────────────────────────────
    rev = 0.0
    if predicted_revenue_best and predicted_revenue_best > 0:
        rev = max(0.0, min(1.0, predicted_revenue_best / 20_000_000))

    # ── 13. Time context ───────────────────────────────────────────────
    try:
        from shared.utils.business_hours import (
            get_time_of_day_bucket,
        )
        from shared.utils.business_hours import (
            is_business_hours as _is_bh,
        )

        _time_bucket = get_time_of_day_bucket()
        _bh = _is_bh()
    except Exception:
        _time_bucket = "afternoon"
        _bh = True

    return SignalVector(
        # Normalised scores
        engagement_score=round(engagement, 4),
        health_score=round(health_norm, 4),
        confidence_score=round(conf, 4),
        contact_quality=round(cq, 2),
        temperature_score=temp_score,
        recency_score=recency,
        pipeline_progress=pipeline,
        objection_score=round(obj_score, 2),
        intent_strength=intent_str,
        closing_progress=round(closing_prog, 2),
        followup_pressure=round(fu_pressure, 2),
        revenue_potential=round(rev, 4),
        # Boolean flags
        phone_captured=phone_captured,
        has_area=has_area or area_m2 is not None,
        has_district=has_district,
        closing_attempted=closing_attempted,
        objection_resolved=objection_resolved,
        negotiation_escalated=negotiation_escalated,
        # Raw context
        area_m2=area_m2,
        last_objection=last_objection,
        last_objection_severity=last_objection_severity,
        intent=intent,
        lead_temperature=lead_temperature,
        buyer_type=buyer_type,
        current_stage=current_stage,
        design_type=design_type,
        closing_action=closing_action,
        lead_status=lead_status,
        follow_up_count=follow_up_count,
        follow_up_type=follow_up_type,
        follow_up_should=follow_up_should,
        minutes_since_last_activity=minutes_since_last_activity,
        last_activity_ts=last_activity_ts,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        predicted_revenue_best=predicted_revenue_best,
        predicted_revenue_max=predicted_revenue_max,
        # Time context
        time_of_day_bucket=_time_bucket,
        is_business_hours=_bh,
        # Original scores
        lead_score_raw=lead_score,
        health_score_raw=health_score,
        closing_confidence_raw=closing_confidence,
        deal_probability_percent=deal_probability_percent,
    )


def with_deal_probability(
    sv: SignalVector,
    dp_percent: int,
) -> SignalVector:
    """Return a copy of *sv* with deal_probability_percent set.

    Use after computing deal probability so downstream engines
    (closing_readiness, radar) can reference it.
    """
    return dc_replace(sv, deal_probability_percent=dp_percent)
