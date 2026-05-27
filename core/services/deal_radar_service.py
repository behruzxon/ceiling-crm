"""
core.services.deal_radar_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Ranks leads by urgency and business value so admins know which lead
to work on right now.

Pure deterministic function — no I/O, fully testable.

Radar buckets (highest → lowest priority):
  1. attack_now   — high probability, high revenue, close-ready, warming up
  2. work_today   — warm/high value but not immediate urgency
  3. nurture      — researching / stable engagement, needs drip
  4. revive       — delayed / reactivated, needs re-engagement
  5. low_priority  — cold, low score, low revenue

Usage::

    from core.services.deal_radar_service import rank_lead_for_radar

    result = rank_lead_for_radar(
        score=75,
        deal_probability_percent=82,
        predicted_revenue_best=12_000_000,
        decision_stage="close_ready",
        engagement_trend="warming_up",
        phone_captured=True,
    )
    # result.radar_bucket == "attack_now"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.services.signal_vector_service import SignalVector


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RadarResult:
    """Radar ranking for a single lead."""

    radar_priority_score: int
    """0-100 composite priority score."""

    radar_bucket: str
    """One of: attack_now, work_today, nurture, revive, low_priority."""

    radar_reason: str
    """Human-readable explanation of the ranking."""

    recommended_immediate_action: str
    """Short Uzbek action recommendation for the admin."""

    radar_signals: list[str] = field(default_factory=list)
    """Key signals that contributed to the score."""


# ── Bucket constants ─────────────────────────────────────────────────────────

BUCKET_ATTACK_NOW = "attack_now"
BUCKET_WORK_TODAY = "work_today"
BUCKET_NURTURE = "nurture"
BUCKET_REVIVE = "revive"
BUCKET_LOW_PRIORITY = "low_priority"

BUCKET_LABELS: dict[str, str] = {
    BUCKET_ATTACK_NOW: "🔴 Hozir hujum",
    BUCKET_WORK_TODAY: "🟠 Bugun ishlang",
    BUCKET_NURTURE: "🟡 Rivojlantiring",
    BUCKET_REVIVE: "🔵 Qayta tiklang",
    BUCKET_LOW_PRIORITY: "⚪ Past prioritet",
}

BUCKET_ORDER: dict[str, int] = {
    BUCKET_ATTACK_NOW: 0,
    BUCKET_WORK_TODAY: 1,
    BUCKET_NURTURE: 2,
    BUCKET_REVIVE: 3,
    BUCKET_LOW_PRIORITY: 4,
}


# ── Main ranking function ────────────────────────────────────────────────────


def rank_lead_for_radar(
    *,
    score: int = 0,
    deal_probability_percent: int | None = None,
    predicted_revenue_best: int | None = None,
    predicted_revenue_max: int | None = None,
    buyer_type: str | None = None,
    negotiation_escalated: bool = False,
    decision_stage: str | None = None,
    engagement_trend: str | None = None,
    follow_up_should: bool = True,
    follow_up_type: str | None = None,
    phone_captured: bool = False,
    has_area: bool = False,
    has_district: bool = False,
    closing_attempted: bool = False,
    closing_confidence: float | None = None,
    lead_temperature: str | None = None,
    lead_status: str | None = None,
    follow_up_count: int = 0,
    last_activity_ts: int | None = None,
    signal_vector: SignalVector | None = None,
) -> RadarResult:
    """Compute radar priority for a single lead.

    When *signal_vector* is provided, uses normalised scores with
    rebalanced weights that eliminate double-counting.  Otherwise
    falls back to legacy per-parameter scoring for backward compat.
    """
    if signal_vector is not None:
        return _rank_from_vector(signal_vector)

    return _rank_legacy(
        score=score,
        deal_probability_percent=deal_probability_percent,
        predicted_revenue_best=predicted_revenue_best,
        predicted_revenue_max=predicted_revenue_max,
        negotiation_escalated=negotiation_escalated,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        follow_up_type=follow_up_type,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        closing_attempted=closing_attempted,
        closing_confidence=closing_confidence,
        lead_temperature=lead_temperature,
        lead_status=lead_status,
        last_activity_ts=last_activity_ts,
    )


# ── SignalVector-based scoring (no double-counting) ─────────────────────────
#
#   Component                   Max contribution
#   ──────────────────────────────────────────────
#   Deal probability             30  (dp × 0.30)
#   Revenue potential            20  (revenue_potential × 20)
#   Engagement (pure)            18  (engagement_score × 18)
#   Decision stage               15  (stage mapping)
#   Engagement trend             10  (trend mapping)
#   Contact quality               5  (contact_quality × 5)
#   Closing progress              3  (closing_progress × 3)
#   Escalation bonus              5
#   Freshness ±                   5
#   Temperature ±                 3
#   ──────────────────────────────────────────────
#   Subtotal max               ~114 → clamp 100


def _rank_from_vector(sv: SignalVector) -> RadarResult:
    """Score using normalised SignalVector — no double-counting."""
    signals: list[str] = []
    pts = 0.0

    dp = sv.deal_probability_percent or 0

    # ── Terminal status ──────────────────────────────────────────
    if sv.lead_status in ("deal", "lost"):
        bucket = BUCKET_LOW_PRIORITY
        reason = "Terminal status" if sv.lead_status == "lost" else "Won"
        return RadarResult(
            radar_priority_score=0,
            radar_bucket=bucket,
            radar_reason=reason,
            recommended_immediate_action="Hech narsa — tugallangan",
            radar_signals=[f"status:{sv.lead_status}"],
        )

    # ── 1. Deal probability (max 30) ────────────────────────────
    pts += min(dp * 0.3, 30)
    if dp >= 70:
        signals.append("yuqori ehtimol")
    elif dp >= 40:
        signals.append("o'rta ehtimol")

    # ── 2. Revenue potential (max 20) ────────────────────────────
    pts += sv.revenue_potential * 20
    rev = sv.predicted_revenue_best or 0
    if rev >= 10_000_000:
        signals.append("yuqori daromad")
    elif rev >= 5_000_000:
        signals.append("o'rta daromad")

    # ── 3. Pure engagement (max 18) ──────────────────────────────
    pts += sv.engagement_score * 18
    if sv.engagement_score >= 0.6:
        signals.append("hot ball")
    elif sv.engagement_score >= 0.3:
        signals.append("warm ball")

    # ── 4. Decision stage (0-15) ─────────────────────────────────
    _stage_pts: dict[str, float] = {
        "close_ready": 15,
        "negotiating": 12,
        "comparing": 8,
        "researching": 5,
        "new_interest": 3,
        "delayed": 2,
        "cold": 0,
    }
    pts += _stage_pts.get(sv.decision_stage or "", 3)
    if sv.decision_stage:
        signals.append(sv.decision_stage)

    # ── 5. Engagement trend (0-10) ───────────────────────────────
    _trend_pts: dict[str, float] = {
        "warming_up": 10,
        "reactivated": 7,
        "stable": 5,
        "cooling_down": 2,
    }
    pts += _trend_pts.get(sv.engagement_trend or "", 3)
    if sv.engagement_trend:
        signals.append(sv.engagement_trend)

    # ── 6. Contact quality (max 5) ───────────────────────────────
    pts += sv.contact_quality * 5
    if sv.phone_captured:
        signals.append("telefon bor")
    if sv.has_area:
        signals.append("maydon bor")

    # ── 7. Closing progress (max 3) ──────────────────────────────
    pts += sv.closing_progress * 3
    if sv.closing_attempted:
        signals.append("closing urinilgan")

    # ── 8. Escalation bonus (+5) ─────────────────────────────────
    if sv.negotiation_escalated:
        pts += 5
        signals.append("ESCALATE")

    # ── 9. Freshness ±5 ──────────────────────────────────────────
    if sv.last_activity_ts:
        import time

        age_hours = (time.time() - sv.last_activity_ts) / 3600
        if age_hours < 1:
            pts += 5
            signals.append("yangi faoliyat")
        elif age_hours < 6:
            pts += 2
        elif age_hours > 48:
            pts -= 5
            signals.append("eski faoliyat")

    # ── 10. Temperature ±3 ───────────────────────────────────────
    pts += sv.temperature_score * 3
    if sv.temperature_score <= 0:
        pts -= 2

    # ── Clamp ────────────────────────────────────────────────────
    priority_score = max(0, min(100, int(pts)))

    # ── Determine bucket ─────────────────────────────────────────
    bucket = _determine_bucket(
        priority_score=priority_score,
        decision_stage=sv.decision_stage,
        engagement_trend=sv.engagement_trend,
        dp=dp,
        rev=rev,
        score=sv.lead_score_raw,
        lead_temperature=sv.lead_temperature,
        negotiation_escalated=sv.negotiation_escalated,
    )

    reason = ", ".join(signals[:5]) if signals else f"ball: {sv.lead_score_raw}"

    action = _pick_action(
        bucket=bucket,
        phone_captured=sv.phone_captured,
        has_area=sv.has_area,
        closing_attempted=sv.closing_attempted,
        negotiation_escalated=sv.negotiation_escalated,
        follow_up_type=sv.follow_up_type,
    )

    return RadarResult(
        radar_priority_score=priority_score,
        radar_bucket=bucket,
        radar_reason=reason,
        recommended_immediate_action=action,
        radar_signals=signals,
    )


# ── Legacy scoring (backward compat) ────────────────────────────────────────


def _rank_legacy(
    *,
    score: int,
    deal_probability_percent: int | None,
    predicted_revenue_best: int | None,
    predicted_revenue_max: int | None,
    negotiation_escalated: bool,
    decision_stage: str | None,
    engagement_trend: str | None,
    follow_up_type: str | None,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
    closing_attempted: bool,
    closing_confidence: float | None,
    lead_temperature: str | None,
    lead_status: str | None,
    last_activity_ts: int | None,
) -> RadarResult:
    signals: list[str] = []
    pts = 0.0

    dp = deal_probability_percent or 0
    rev = predicted_revenue_best or 0

    if lead_status in ("deal", "lost"):
        bucket = BUCKET_LOW_PRIORITY
        reason = "Terminal status" if lead_status == "lost" else "Won"
        return RadarResult(
            radar_priority_score=0,
            radar_bucket=bucket,
            radar_reason=reason,
            recommended_immediate_action="Hech narsa — tugallangan",
            radar_signals=[f"status:{lead_status}"],
        )

    prob_pts = min(dp * 0.3, 30)
    pts += prob_pts
    if dp >= 70:
        signals.append("yuqori ehtimol")
    elif dp >= 40:
        signals.append("o'rta ehtimol")

    if rev > 0:
        rev_pts = min(rev / 1_000_000, 20)
        pts += rev_pts
        if rev >= 10_000_000:
            signals.append("yuqori daromad")
        elif rev >= 5_000_000:
            signals.append("o'rta daromad")

    score_pts = min(score * 0.15, 15)
    pts += score_pts
    if score >= 60:
        signals.append("hot ball")
    elif score >= 30:
        signals.append("warm ball")

    _stage_pts: dict[str, float] = {
        "close_ready": 15,
        "negotiating": 12,
        "comparing": 8,
        "researching": 5,
        "new_interest": 3,
        "delayed": 2,
        "cold": 0,
    }
    stage_pts = _stage_pts.get(decision_stage or "", 3)
    pts += stage_pts
    if decision_stage:
        signals.append(decision_stage)

    _trend_pts: dict[str, float] = {
        "warming_up": 10,
        "reactivated": 7,
        "stable": 5,
        "cooling_down": 2,
    }
    trend_pts = _trend_pts.get(engagement_trend or "", 3)
    pts += trend_pts
    if engagement_trend:
        signals.append(engagement_trend)

    if phone_captured:
        pts += 3
        signals.append("telefon bor")
    if has_area:
        pts += 2
        signals.append("maydon bor")
    if has_district:
        pts += 1
    if closing_attempted:
        pts += 2
        signals.append("closing urinilgan")
    if closing_confidence and closing_confidence >= 0.7:
        pts += 2
        signals.append("yuqori ishonch")

    if negotiation_escalated:
        pts += 5
        signals.append("ESCALATE")

    if last_activity_ts:
        import time

        age_hours = (time.time() - last_activity_ts) / 3600
        if age_hours < 1:
            pts += 5
            signals.append("yangi faoliyat")
        elif age_hours < 6:
            pts += 2
        elif age_hours > 48:
            pts -= 5
            signals.append("eski faoliyat")

    if lead_temperature == "hot":
        pts += 3
    elif lead_temperature == "warm":
        pts += 1
    elif lead_temperature == "cold":
        pts -= 2

    priority_score = max(0, min(100, int(pts)))

    bucket = _determine_bucket(
        priority_score=priority_score,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        dp=dp,
        rev=rev,
        score=score,
        lead_temperature=lead_temperature,
        negotiation_escalated=negotiation_escalated,
    )

    reason = ", ".join(signals[:5]) if signals else f"ball: {score}"

    action = _pick_action(
        bucket=bucket,
        phone_captured=phone_captured,
        has_area=has_area,
        closing_attempted=closing_attempted,
        negotiation_escalated=negotiation_escalated,
        follow_up_type=follow_up_type,
    )

    return RadarResult(
        radar_priority_score=priority_score,
        radar_bucket=bucket,
        radar_reason=reason,
        recommended_immediate_action=action,
        radar_signals=signals,
    )


def _determine_bucket(
    *,
    priority_score: int,
    decision_stage: str | None,
    engagement_trend: str | None,
    dp: int,
    rev: int,
    score: int,
    lead_temperature: str | None,
    negotiation_escalated: bool,
) -> str:
    """Assign a radar bucket based on priority score + context signals."""

    # Rule 1: close_ready + warming + high prob → attack_now
    if decision_stage == "close_ready" and engagement_trend == "warming_up" and dp >= 60:
        return BUCKET_ATTACK_NOW

    # Rule 2: escalation flag → attack_now
    if negotiation_escalated and priority_score >= 40:
        return BUCKET_ATTACK_NOW

    # Rule 3: high priority score
    if priority_score >= 75:
        return BUCKET_ATTACK_NOW
    if priority_score >= 50:
        return BUCKET_WORK_TODAY

    # Rule 4: delayed or reactivated → revive
    if decision_stage in ("delayed", "cold") and engagement_trend == "reactivated":
        return BUCKET_REVIVE
    if decision_stage == "delayed":
        return BUCKET_REVIVE

    # Rule 5: researching/stable → nurture
    if decision_stage in ("researching", "new_interest", "comparing"):
        if engagement_trend in ("stable", "warming_up"):
            return BUCKET_NURTURE

    # Rule 6: cold + low score + low revenue → low_priority
    if lead_temperature == "cold" and score < 20 and (rev < 3_000_000 or rev == 0):
        return BUCKET_LOW_PRIORITY

    # Rule 7: negotiating/comparing with decent signals → work_today
    if decision_stage in ("negotiating", "comparing") and priority_score >= 35:
        return BUCKET_WORK_TODAY

    # Rule 8: cooling_down → revive if enough value
    if engagement_trend == "cooling_down":
        if dp >= 30 or score >= 30:
            return BUCKET_REVIVE
        return BUCKET_LOW_PRIORITY

    # Default by score thresholds
    if priority_score >= 35:
        return BUCKET_NURTURE
    if priority_score >= 20:
        return BUCKET_LOW_PRIORITY
    return BUCKET_LOW_PRIORITY


def _pick_action(
    *,
    bucket: str,
    phone_captured: bool,
    has_area: bool,
    closing_attempted: bool,
    negotiation_escalated: bool,
    follow_up_type: str | None,
) -> str:
    """Pick a short recommended action based on bucket + signals."""
    if bucket == BUCKET_ATTACK_NOW:
        if negotiation_escalated:
            return "Manager qo'ng'iroq qilsin — 5 daqiqa ichida"
        if phone_captured:
            return "10 daqiqa ichida qo'ng'iroq qiling"
        if has_area:
            return "Bepul o'lchov taklif qiling"
        return "Hozir yozing — closing taklif qiling"

    if bucket == BUCKET_WORK_TODAY:
        if phone_captured:
            return "Bugun qo'ng'iroq qiling"
        if has_area and not closing_attempted:
            return "O'lchov yoki narx taklif qiling"
        return "Bugun xabar yuboring"

    if bucket == BUCKET_NURTURE:
        return "Katalog yoki narx yuborish"

    if bucket == BUCKET_REVIVE:
        if follow_up_type == "soft_reactivation":
            return "Yumshoq salomlashing"
        return "Qayta aloqa qiling"

    return "Kutib turing"


# ── Batch ranking ─────────────────────────────────────────────────────────────


def rank_leads_for_radar(
    leads: list[dict],
    *,
    top_n: int = 5,
) -> list[dict]:
    """Rank a list of lead signal dicts and return top N sorted by priority.

    Each dict in *leads* must contain a ``lead_id`` key plus any keyword
    arguments accepted by :func:`rank_lead_for_radar`.

    Returns dicts augmented with radar result fields, sorted by
    (bucket_order ASC, priority_score DESC).
    """
    results: list[dict] = []
    for lead_signals in leads:
        lead_id = lead_signals.get("lead_id", 0)
        kwargs = {k: v for k, v in lead_signals.items() if k != "lead_id"}
        result = rank_lead_for_radar(**kwargs)
        results.append(
            {
                "lead_id": lead_id,
                "radar_priority_score": result.radar_priority_score,
                "radar_bucket": result.radar_bucket,
                "radar_reason": result.radar_reason,
                "recommended_immediate_action": result.recommended_immediate_action,
                "radar_signals": result.radar_signals,
            }
        )

    # Sort: bucket order first, then priority score desc
    results.sort(
        key=lambda r: (
            BUCKET_ORDER.get(r["radar_bucket"], 99),
            -r["radar_priority_score"],
        ),
    )
    return results[:top_n]
