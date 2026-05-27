"""
core.services.closing_readiness_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Closing Readiness Engine — composite readiness scoring, tactic selection,
message generation, and close-loss risk detection.

Pure deterministic functions — no I/O, fully testable.

Readiness tiers:
  - NOT_READY     (score <30)   — lead needs nurturing
  - NEAR_CLOSE    (score 30-69) — getting warm, keep engaging
  - READY_TO_CLOSE (score 70+)  — push for conversion now

Usage::

    from core.services.closing_readiness_service import (
        evaluate_closing_readiness,
        select_closing_tactic,
    )

    cr = evaluate_closing_readiness(score=72, health_score=68, ...)
    # cr.readiness_tier == "READY_TO_CLOSE"
    # cr.closing_score == 84
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.services.signal_vector_service import SignalVector


# ── Readiness tiers ─────────────────────────────────────────────────────────

TIER_NOT_READY = "NOT_READY"
TIER_NEAR_CLOSE = "NEAR_CLOSE"
TIER_READY_TO_CLOSE = "READY_TO_CLOSE"

TIER_LABELS: dict[str, str] = {
    TIER_NOT_READY: "Tayyor emas",
    TIER_NEAR_CLOSE: "Yaqin",
    TIER_READY_TO_CLOSE: "Yopishga tayyor",
}

TIER_BADGES: dict[str, str] = {
    TIER_NOT_READY: "\u26aa",
    TIER_NEAR_CLOSE: "\U0001f7e1",
    TIER_READY_TO_CLOSE: "\U0001f534",
}


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ClosingReadiness:
    """Composite closing readiness assessment."""

    closing_score: int
    """0-100 composite readiness score."""

    readiness_tier: str
    """'NOT_READY' | 'NEAR_CLOSE' | 'READY_TO_CLOSE'."""

    confidence: str
    """'low' | 'medium' | 'high'."""

    reason: str
    """English machine-readable reason."""

    reason_uz: str
    """Uzbek reason for admin display."""

    suggested_timeline_hours: int
    """Suggested hours within which to attempt close (0=now)."""

    close_probability: float
    """0.0–1.0 estimated probability of successful close."""

    signals: list[str] = field(default_factory=list)
    """Positive signals that contributed to the score."""

    blockers: list[str] = field(default_factory=list)
    """Negative factors reducing readiness."""


@dataclass(frozen=True, slots=True)
class ClosingTacticResult:
    """Selected closing tactic with message."""

    tactic: str
    """Machine-readable tactic key."""

    tactic_uz: str
    """Uzbek label for admin."""

    reason_uz: str
    """Why this tactic was chosen."""

    suggested_message_uz: str
    """Ready-to-send Uzbek closing message."""

    confidence: float
    """0.0–1.0 confidence in tactic success."""

    fallback_message_uz: str
    """Alternative softer message if primary feels too aggressive."""


@dataclass(frozen=True, slots=True)
class CloseLossRisk:
    """Risk of losing a close-ready lead."""

    detected: bool
    risk_level: str
    """'none' | 'warning' | 'critical'."""

    minutes_waiting: int
    risk_reason_uz: str
    recommended_action_uz: str
    risk_signals: list[str] = field(default_factory=list)


# ── Tactic catalogue ────────────────────────────────────────────────────────

TACTIC_LABELS: dict[str, str] = {
    "urgency_close": "Shoshilinch taklif",
    "bonus_offer": "Bonus taklif",
    "measurement_booking": "O'lchov rejalashtirish",
    "simplified_package_close": "Sodda paket taklifi",
    "trust_reassurance_close": "Ishonch mustahkamlash",
    "manager_direct_call": "Menejer qo'ng'iroq",
}

_TACTIC_MESSAGES: dict[str, str] = {
    "urgency_close": (
        "Assalomu alaykum! Bu oy oxirigacha maxsus narx amal qilmoqda. "
        "Hoziroq buyurtma bersangiz, eng yaxshi shartlarda amalga oshiramiz!"
    ),
    "bonus_offer": (
        "Sizga maxsus bonus: buyurtma qilsangiz, "
        "bepul o'rnatish xizmati va LED yoritgich sovg'a! "
        "Qiziqsangiz, yozing \U0001f60a"
    ),
    "measurement_booking": (
        "Assalomu alaykum! Agar xohlasangiz, ustamiz bepul o'lchov "
        "qilib berishi mumkin. Qaysi vaqt sizga qulay bo'ladi?"
    ),
    "simplified_package_close": (
        "Sizning xonangiz uchun eng mos variant tayyorladik \u2014 "
        "oddiy va arzon. Tafsilotlar kerakmi?"
    ),
    "trust_reassurance_close": (
        "Bizning barcha ishlarimiz kafolat bilan. "
        "100+ mijoz ishonch bildirgan. "
        "Rasmlarni ko'rsatib beraymi?"
    ),
    "manager_direct_call": (
        "Menejerimiz sizga qo'ng'iroq qilib, barcha savollaringizga "
        "javob berishi mumkin. Qaysi vaqt qulay?"
    ),
}

_TACTIC_FALLBACKS: dict[str, str] = {
    "urgency_close": ("Narxlar tez o'zgarishi mumkin. " "Hozirgi sharoitda hisoblab bersinmi?"),
    "bonus_offer": ("Qo'shimcha xizmatlarimiz haqida ma'lumot beraymi?"),
    "measurement_booking": ("Bepul maslahat olishni xohlaysizmi? " "Hech qanday majburiyat yo'q."),
    "simplified_package_close": ("Eng oddiy variantimiz haqida aytib beraymi?"),
    "trust_reassurance_close": ("Oldingi ishlarimiz fotosini ko'rmoqchimisiz?"),
    "manager_direct_call": ("Savollaringiz bo'lsa, yozing \u2014 yordam beramiz!"),
}


# ── Closing Readiness Engine ────────────────────────────────────────────────


def evaluate_closing_readiness(
    *,
    score: int = 0,
    health_score: int = 50,
    last_objection: str | None = None,
    last_objection_severity: str | None = None,
    objection_resolved: bool = False,
    minutes_since_last_activity: int = 0,
    current_stage: str | None = None,
    phone_captured: bool = False,
    area_m2: float | None = None,
    has_district: bool = False,
    follow_up_count: int = 0,
    closing_confidence: float | None = None,
    lead_temperature: str | None = None,
    buyer_type: str | None = None,
    closing_attempted: bool = False,
    deal_probability_percent: int | None = None,
    signal_vector: SignalVector | None = None,
) -> ClosingReadiness:
    """Evaluate composite closing readiness for a lead.

    When *signal_vector* is provided, uses normalised scores with
    rebalanced weights that eliminate double-counting.  Otherwise
    falls back to legacy per-parameter scoring for backward compat.
    """
    if signal_vector is not None:
        return _evaluate_readiness_from_vector(signal_vector)

    return _evaluate_readiness_legacy(
        score=score,
        health_score=health_score,
        last_objection=last_objection,
        last_objection_severity=last_objection_severity,
        objection_resolved=objection_resolved,
        minutes_since_last_activity=minutes_since_last_activity,
        current_stage=current_stage,
        phone_captured=phone_captured,
        area_m2=area_m2,
        has_district=has_district,
        follow_up_count=follow_up_count,
        closing_confidence=closing_confidence,
        lead_temperature=lead_temperature,
        closing_attempted=closing_attempted,
        deal_probability_percent=deal_probability_percent,
    )


# ── SignalVector-based scoring (no double-counting) ─────────────────────────
#
#   Component                   Max contribution
#   ──────────────────────────────────────────────
#   Contact quality              28  (contact_quality × 28)
#   Engagement (pure)            25  (engagement_score × 25)
#   AI closing confidence        15  (confidence_score × 15)
#   Conversation health          10  (health_score × 10)
#   Deal probability boost       10  (dp/100 × 10)
#   Pipeline progress             8  (pipeline_progress × 8)
#   Recency                       8  (recency_score × 8)
#   Closing progress              5  (closing_progress × 5)
#   Temperature                   5
#   Objection: resolved          +8 / none +5 / sev penalty
#   Follow-up fatigue            -8
#   ──────────────────────────────────────────────
#   Subtotal max               ~122 → clamp 100


def _evaluate_readiness_from_vector(sv: SignalVector) -> ClosingReadiness:
    """Score using normalised SignalVector — no double-counting."""
    signals: list[str] = []
    blockers: list[str] = []
    pts = 0.0

    dp = sv.deal_probability_percent or 0

    # ── Contact quality (max 28) ─────────────────────────────────
    pts += sv.contact_quality * 28
    if sv.phone_captured:
        signals.append("phone_captured")
    else:
        blockers.append("no_phone")
    if sv.has_area:
        signals.append("area_known")
    if sv.has_district:
        signals.append("district_known")

    # ── Pure engagement (max 25) ─────────────────────────────────
    pts += sv.engagement_score * 25
    if sv.engagement_score >= 0.7:
        signals.append("very_high_score")
    elif sv.engagement_score >= 0.5:
        signals.append("high_score")
    elif sv.engagement_score >= 0.3:
        signals.append("moderate_score")

    # ── AI closing confidence (max 15) ───────────────────────────
    pts += sv.confidence_score * 15
    if sv.confidence_score >= 0.7:
        signals.append("high_confidence")
    elif sv.confidence_score >= 0.4:
        signals.append("moderate_confidence")
    elif 0 < sv.confidence_score < 0.2:
        blockers.append("low_confidence")

    # ── Conversation health (max 10) ─────────────────────────────
    pts += sv.health_score * 10
    if sv.health_score >= 0.7:
        signals.append("healthy_conversation")
    elif sv.health_score < 0.3:
        pts -= 5
        blockers.append("poor_conversation_health")

    # ── Deal probability boost (max 10) ──────────────────────────
    if dp >= 70:
        pts += 10
        signals.append("high_deal_probability")
    elif dp >= 50:
        pts += 5

    # ── Pipeline progress (max 8) ────────────────────────────────
    pts += sv.pipeline_progress * 8
    if sv.pipeline_progress >= 0.6:
        signals.append("advanced_stage")

    # ── Objection impact ─────────────────────────────────────────
    if sv.last_objection:
        if sv.objection_resolved:
            pts += 8
            signals.append("objection_resolved")
        else:
            severity_penalty = {"low": -3, "medium": -8, "high": -15}
            pts += severity_penalty.get(
                (sv.last_objection_severity or "low").lower(),
                -3,
            )
            blockers.append(f"unresolved_{sv.last_objection}")
    else:
        pts += 5
        signals.append("no_objection")

    # ── Recency (max 8) ─────────────────────────────────────────
    pts += sv.recency_score * 8
    if sv.recency_score >= 0.8:
        signals.append("very_recent_activity")
    elif sv.recency_score >= 0.5:
        signals.append("recent_activity")
    elif sv.recency_score == 0.0:
        blockers.append("inactive_6h_plus")

    # ── Closing progress (max 5) ─────────────────────────────────
    pts += sv.closing_progress * 5
    if sv.closing_attempted:
        signals.append("prior_closing_attempt")

    # ── Follow-up fatigue ────────────────────────────────────────
    if sv.followup_pressure >= 1.0:
        pts -= 8
        blockers.append("followup_fatigue")
    elif sv.followup_pressure >= 0.6:
        pts -= 3

    # ── Temperature bonus (max 5) ────────────────────────────────
    pts += sv.temperature_score * 5
    if sv.temperature_score >= 1.0:
        signals.append("hot_temperature")

    # ── Clamp & classify ─────────────────────────────────────────
    closing_score = max(0, min(100, int(pts)))

    if closing_score >= 70:
        tier = TIER_READY_TO_CLOSE
    elif closing_score >= 30:
        tier = TIER_NEAR_CLOSE
    else:
        tier = TIER_NOT_READY

    strong_signals = len(signals)
    if strong_signals >= 6:
        confidence = "high"
    elif strong_signals >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    close_prob = min(1.0, closing_score / 100 * 1.1)
    if dp:
        close_prob = (close_prob + dp / 100) / 2

    temp = (sv.lead_temperature or "").lower()
    mins = sv.minutes_since_last_activity
    if tier == TIER_READY_TO_CLOSE:
        timeline = 0 if mins <= 60 else 2
    elif tier == TIER_NEAR_CLOSE:
        timeline = 6 if temp == "hot" else 24
    else:
        timeline = 48

    reason = _build_reason(signals, blockers)
    reason_uz = _build_reason_uz(tier, signals, blockers)

    return ClosingReadiness(
        closing_score=closing_score,
        readiness_tier=tier,
        confidence=confidence,
        reason=reason,
        reason_uz=reason_uz,
        suggested_timeline_hours=timeline,
        close_probability=round(close_prob, 2),
        signals=signals[:8],
        blockers=blockers[:5],
    )


# ── Legacy scoring (backward compat) ────────────────────────────────────────


def _evaluate_readiness_legacy(
    *,
    score: int,
    health_score: int,
    last_objection: str | None,
    last_objection_severity: str | None,
    objection_resolved: bool,
    minutes_since_last_activity: int,
    current_stage: str | None,
    phone_captured: bool,
    area_m2: float | None,
    has_district: bool,
    follow_up_count: int,
    closing_confidence: float | None,
    lead_temperature: str | None,
    closing_attempted: bool,
    deal_probability_percent: int | None,
) -> ClosingReadiness:
    signals: list[str] = []
    blockers: list[str] = []
    pts = 0

    conf = closing_confidence or 0.0
    dp = deal_probability_percent or 0
    temp = (lead_temperature or "").lower()
    stage = (current_stage or "NEW").upper()

    if phone_captured:
        pts += 20
        signals.append("phone_captured")
    else:
        blockers.append("no_phone")

    if area_m2 is not None:
        pts += 12
        signals.append("area_known")

    if has_district:
        pts += 5
        signals.append("district_known")

    if score >= 70:
        pts += 20
        signals.append("very_high_score")
    elif score >= 50:
        pts += 14
        signals.append("high_score")
    elif score >= 30:
        pts += 7
        signals.append("moderate_score")

    if conf >= 0.7:
        pts += 15
        signals.append("high_confidence")
    elif conf >= 0.4:
        pts += 8
        signals.append("moderate_confidence")
    elif conf < 0.2 and conf > 0:
        blockers.append("low_confidence")

    if health_score >= 70:
        pts += 10
        signals.append("healthy_conversation")
    elif health_score >= 50:
        pts += 5
    elif health_score < 30:
        pts -= 5
        blockers.append("poor_conversation_health")

    if dp >= 70:
        pts += 10
        signals.append("high_deal_probability")
    elif dp >= 50:
        pts += 5

    _stage_pts = {
        "DEAL": 8,
        "QUOTE": 6,
        "MEASUREMENT": 5,
        "CONTACTED": 3,
        "PACKAGE_SELECTED": 2,
    }
    stage_bonus = _stage_pts.get(stage, 0)
    if stage_bonus:
        pts += stage_bonus
        if stage in ("DEAL", "QUOTE"):
            signals.append("advanced_stage")

    if last_objection:
        if objection_resolved:
            pts += 8
            signals.append("objection_resolved")
        else:
            severity_penalty = {"low": -3, "medium": -8, "high": -15}
            pts += severity_penalty.get(last_objection_severity or "low", -3)
            blockers.append(f"unresolved_{last_objection}")
    else:
        pts += 5
        signals.append("no_objection")

    if minutes_since_last_activity <= 30:
        pts += 8
        signals.append("very_recent_activity")
    elif minutes_since_last_activity <= 120:
        pts += 4
        signals.append("recent_activity")
    elif minutes_since_last_activity >= 360:
        pts -= 5
        blockers.append("inactive_6h_plus")

    if closing_attempted:
        pts += 3
        signals.append("prior_closing_attempt")

    if follow_up_count >= 5:
        pts -= 8
        blockers.append("followup_fatigue")
    elif follow_up_count >= 3:
        pts -= 3

    if temp == "hot":
        pts += 5
        signals.append("hot_temperature")

    closing_score = max(0, min(100, pts))

    if closing_score >= 70:
        tier = TIER_READY_TO_CLOSE
    elif closing_score >= 30:
        tier = TIER_NEAR_CLOSE
    else:
        tier = TIER_NOT_READY

    strong_signals = len(signals)
    if strong_signals >= 6:
        confidence = "high"
    elif strong_signals >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    close_prob = min(1.0, closing_score / 100 * 1.1)
    if dp:
        close_prob = (close_prob + dp / 100) / 2

    if tier == TIER_READY_TO_CLOSE:
        timeline = 0 if minutes_since_last_activity <= 60 else 2
    elif tier == TIER_NEAR_CLOSE:
        timeline = 6 if temp == "hot" else 24
    else:
        timeline = 48

    reason = _build_reason(signals, blockers)
    reason_uz = _build_reason_uz(tier, signals, blockers)

    return ClosingReadiness(
        closing_score=closing_score,
        readiness_tier=tier,
        confidence=confidence,
        reason=reason,
        reason_uz=reason_uz,
        suggested_timeline_hours=timeline,
        close_probability=round(close_prob, 2),
        signals=signals[:8],
        blockers=blockers[:5],
    )


# ── Closing Tactic Selector ────────────────────────────────────────────────


def select_closing_tactic(
    *,
    readiness_tier: str,
    closing_score: int = 0,
    last_objection: str | None = None,
    objection_resolved: bool = False,
    buyer_type: str | None = None,
    phone_captured: bool = False,
    area_m2: float | None = None,
    closing_attempted: bool = False,
    minutes_since_last_activity: int = 0,
    follow_up_count: int = 0,
    lead_temperature: str | None = None,
) -> ClosingTacticResult:
    """Select the optimal closing tactic based on lead readiness and context.

    Only suggests aggressive tactics for READY_TO_CLOSE leads.
    NEAR_CLOSE leads get softer approaches.
    NOT_READY leads get measurement_booking or trust_reassurance.
    """
    temp = (lead_temperature or "").lower()

    # ── NOT_READY: soft approach only ────────────────────────────
    if readiness_tier == TIER_NOT_READY:
        if phone_captured:
            tactic = "measurement_booking"
            reason = "Lid tayyor emas, lekin telefon bor \u2014 yumshoq o'lchov taklifi"
        else:
            tactic = "trust_reassurance_close"
            reason = "Lid tayyor emas \u2014 ishonchni mustahkamlang"
        return _build_tactic_result(tactic, reason, confidence=0.30)

    # ── NEAR_CLOSE: moderate approach ────────────────────────────
    if readiness_tier == TIER_NEAR_CLOSE:
        # Price objection → simplified package
        if last_objection in ("expensive", "compare") and not objection_resolved:
            return _build_tactic_result(
                "simplified_package_close",
                "Narx e'tirozi bor \u2014 sodda paket taklif qiling",
                confidence=0.50,
            )

        # No phone yet → trust first
        if not phone_captured:
            return _build_tactic_result(
                "trust_reassurance_close",
                "Telefon yo'q \u2014 avval ishonch o'rnating",
                confidence=0.40,
            )

        # Has area → measurement
        if area_m2 is not None:
            return _build_tactic_result(
                "measurement_booking",
                "Maydon ma'lum \u2014 o'lchov rejalashtiring",
                confidence=0.55,
            )

        # Default for NEAR_CLOSE
        return _build_tactic_result(
            "measurement_booking",
            "Lid yaqinlashmoqda \u2014 o'lchov taklif qiling",
            confidence=0.45,
        )

    # ── READY_TO_CLOSE: aggressive approach ──────────────────────

    # Fast buyer → quick scheduling
    if buyer_type == "fast_buyer":
        return _build_tactic_result(
            "measurement_booking",
            "Tez qaror xaridor \u2014 hoziroq o'lchov rejalashtiring",
            confidence=0.85,
        )

    # Price-sensitive with resolved objection → bonus offer
    if buyer_type == "price_sensitive" and objection_resolved:
        return _build_tactic_result(
            "bonus_offer",
            "Narxga sezgir xaridor, e'tiroz hal qilingan \u2014 bonus bering",
            confidence=0.80,
        )

    # Price-sensitive, still objecting → simplified package
    if buyer_type == "price_sensitive" and last_objection in ("expensive", "compare"):
        return _build_tactic_result(
            "simplified_package_close",
            "Narxga sezgir \u2014 sodda paket taklif qiling",
            confidence=0.70,
        )

    # Trust objection → reassurance
    if last_objection == "trust":
        return _build_tactic_result(
            "trust_reassurance_close",
            "Ishonch e'tirozi bor \u2014 natijalar ko'rsating",
            confidence=0.65,
        )

    # Prior close attempt failed → manager call
    if closing_attempted and follow_up_count >= 3:
        return _build_tactic_result(
            "manager_direct_call",
            "Oldingi urinish va follow-uplar bo'lgan \u2014 menejer jalb qiling",
            confidence=0.75,
        )

    # Large area → bonus (high value)
    if area_m2 is not None and area_m2 >= 25:
        return _build_tactic_result(
            "bonus_offer",
            "Katta maydon \u2014 bonus taklif qiling",
            confidence=0.80,
        )

    # Hot + very recent → urgency
    if temp == "hot" and minutes_since_last_activity <= 30:
        return _build_tactic_result(
            "urgency_close",
            "HOT lid va hozir faol \u2014 shoshilinch taklif",
            confidence=0.85,
        )

    # High score + phone → urgency
    if closing_score >= 85 and phone_captured:
        return _build_tactic_result(
            "urgency_close",
            "Juda yuqori tayorlik \u2014 hoziroq yoping",
            confidence=0.85,
        )

    # Default for READY_TO_CLOSE: measurement booking
    return _build_tactic_result(
        "measurement_booking",
        "Lid tayyor \u2014 o'lchov rejalashtiring",
        confidence=0.75,
    )


# ── Close-Loss Risk Detection ──────────────────────────────────────────────


def detect_close_loss_risk(
    *,
    readiness_tier: str,
    closing_score: int = 0,
    minutes_since_last_activity: int = 0,
    health_score: int = 50,
    lead_temperature: str | None = None,
    last_objection: str | None = None,
    objection_resolved: bool = False,
) -> CloseLossRisk:
    """Detect risk of losing a close-ready lead due to delay."""
    signals: list[str] = []
    detected = False
    risk_level = "none"
    temp = (lead_temperature or "").lower()

    # ── READY_TO_CLOSE lead waiting too long ─────────────────────
    if readiness_tier == TIER_READY_TO_CLOSE:
        if minutes_since_last_activity >= 60:
            detected = True
            risk_level = "critical"
            signals.append("ready_lead_waiting_60min")
        elif minutes_since_last_activity >= 30:
            detected = True
            risk_level = "warning"
            signals.append("ready_lead_waiting_30min")

    # ── High score lead cooling ──────────────────────────────────
    if closing_score >= 60 and health_score < 40:
        detected = True
        risk_level = "critical" if risk_level != "critical" else risk_level
        signals.append("high_score_cooling_conversation")

    # ── NEAR_CLOSE HOT lead going silent ─────────────────────────
    if readiness_tier == TIER_NEAR_CLOSE and temp == "hot":
        if minutes_since_last_activity >= 120:
            detected = True
            if risk_level == "none":
                risk_level = "warning"
            signals.append("near_close_hot_inactive_2h")

    # ── Unresolved objection on close-ready lead ─────────────────
    if (
        readiness_tier in (TIER_READY_TO_CLOSE, TIER_NEAR_CLOSE)
        and last_objection
        and not objection_resolved
    ):
        detected = True
        if risk_level == "none":
            risk_level = "warning"
        signals.append("close_ready_unresolved_objection")

    # Build reason
    reasons_uz = []
    if "ready_lead_waiting_60min" in signals:
        reasons_uz.append(f"tayyor lid {minutes_since_last_activity} daqiqa kutmoqda")
    elif "ready_lead_waiting_30min" in signals:
        reasons_uz.append(f"tayyor lid {minutes_since_last_activity} daqiqa kutmoqda")
    if "high_score_cooling_conversation" in signals:
        reasons_uz.append("suhbat sovumoqda")
    if "near_close_hot_inactive_2h" in signals:
        reasons_uz.append("HOT lid 2+ soat javobsiz")
    if "close_ready_unresolved_objection" in signals:
        reasons_uz.append("e'tiroz hal qilinmagan")

    reason_uz = " + ".join(reasons_uz) if reasons_uz else ""

    # Pick action
    if risk_level == "critical":
        action_uz = "Darhol bog'laning yoki o'lchov taklif qiling"
    elif risk_level == "warning":
        action_uz = "Tez follow-up yuboring"
    else:
        action_uz = ""

    return CloseLossRisk(
        detected=detected,
        risk_level=risk_level,
        minutes_waiting=minutes_since_last_activity,
        risk_reason_uz=reason_uz,
        recommended_action_uz=action_uz,
        risk_signals=signals,
    )


# ── HTML Alert Builders ─────────────────────────────────────────────────────


def build_closing_opportunity_alert(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    closing_score: int,
    tactic_uz: str,
    suggested_message_uz: str,
    timeline_hours: int,
) -> str:
    """Build HTML alert for closing opportunity."""
    timeline_str = "hozir" if timeline_hours == 0 else f"{timeline_hours} soat ichida"
    return (
        "\U0001f525 <b>Closing Opportunity</b>\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\U0001f3af Closing Score: {closing_score}/100\n"
        f"\U0001f3c6 Taktika: {tactic_uz}\n"
        f"\u23f0 Vaqt: {timeline_str}\n\n"
        f"\U0001f4ac <b>Taklif:</b>\n"
        f"<code>{suggested_message_uz}</code>"
    )


def build_close_loss_risk_alert(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    minutes_waiting: int,
    risk_reason_uz: str,
    recommended_action_uz: str,
    risk_level: str,
) -> str:
    """Build HTML alert for close-loss risk."""
    _badges = {"warning": "\U0001f7e1", "critical": "\U0001f534"}
    badge = _badges.get(risk_level, "\u26aa")
    return (
        f"\u26a0\ufe0f <b>Close-Loss Risk</b> {badge}\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\u23f0 Kutish: {minutes_waiting} daqiqa\n"
        f"\u26a0\ufe0f Sabab: {risk_reason_uz}\n\n"
        f"<b>Tavsiya:</b> {recommended_action_uz}"
    )


def build_close_advice_card(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    readiness: ClosingReadiness,
    tactic: ClosingTacticResult,
) -> str:
    """Build full close advice card for /close_advice command."""
    tier_label = TIER_LABELS.get(readiness.readiness_tier, readiness.readiness_tier)
    tier_badge = TIER_BADGES.get(readiness.readiness_tier, "\u26aa")
    timeline = (
        "hozir"
        if readiness.suggested_timeline_hours == 0
        else f"{readiness.suggested_timeline_hours} soat ichida"
    )

    lines = [
        f"\U0001f3af <b>Close Advice \u2014 Lead #{lead_id}</b>\n",
        f"\U0001f464 {lead_name} | {lead_phone}",
        f"{tier_badge} Tayorlik: {tier_label} ({readiness.closing_score}/100)",
        f"\U0001f4ca Yopilish ehtimoli: {readiness.close_probability:.0%}",
        f"\U0001f552 Vaqt: {timeline}",
        f"\U0001f4a1 Ishonch: {readiness.confidence}",
        "",
        f"\U0001f3c6 <b>Taktika:</b> {tactic.tactic_uz}",
        f"\U0001f4a1 {tactic.reason_uz}",
        "",
        "\U0001f4ac <b>Asosiy xabar:</b>",
        f"<code>{tactic.suggested_message_uz}</code>",
        "",
        "\U0001f4ac <b>Yumshoq variant:</b>",
        f"<code>{tactic.fallback_message_uz}</code>",
    ]

    # Signals
    if readiness.signals:
        _sig_labels = {
            "phone_captured": "\u2705 Telefon",
            "area_known": "\u2705 Maydon",
            "district_known": "\u2705 Tuman",
            "very_high_score": "\u2b50 Juda yuqori ball",
            "high_score": "\u2b50 Yuqori ball",
            "moderate_score": "\U0001f7e1 O'rta ball",
            "high_confidence": "\u2705 Yuqori ishonch",
            "moderate_confidence": "\U0001f7e1 O'rta ishonch",
            "healthy_conversation": "\u2705 Sog'lom suhbat",
            "high_deal_probability": "\u2705 Yuqori ehtimollik",
            "advanced_stage": "\u2705 Ilg'or bosqich",
            "objection_resolved": "\u2705 E'tiroz hal qilingan",
            "no_objection": "\u2705 E'tiroz yo'q",
            "very_recent_activity": "\u2705 Hozir faol",
            "recent_activity": "\U0001f7e1 Yaqinda faol",
            "prior_closing_attempt": "\U0001f7e1 Oldin urinilgan",
            "hot_temperature": "\U0001f525 HOT",
        }
        lines.append("")
        lines.append("<b>Signallar:</b>")
        for s in readiness.signals[:6]:
            label = _sig_labels.get(s, s)
            lines.append(f"  {label}")

    # Blockers
    if readiness.blockers:
        _blocker_labels = {
            "no_phone": "\u274c Telefon yo'q",
            "low_confidence": "\u274c Past ishonch",
            "poor_conversation_health": "\u274c Suhbat yomon",
            "inactive_6h_plus": "\u274c 6+ soat javobsiz",
            "followup_fatigue": "\u274c Ko'p follow-up",
        }
        lines.append("")
        lines.append("<b>To'siqlar:</b>")
        for b in readiness.blockers[:4]:
            if b.startswith("unresolved_"):
                obj = b.replace("unresolved_", "")
                _obj_uz = {
                    "expensive": "Narx",
                    "compare": "Taqqoslash",
                    "delay": "Kechiktirish",
                    "trust": "Ishonch",
                    "angry": "Norozilik",
                }
                label = f"\u26a0\ufe0f {_obj_uz.get(obj, obj)} e'tirozi ochiq"
            else:
                label = _blocker_labels.get(b, f"\u26a0\ufe0f {b}")
            lines.append(f"  {label}")

    lines.append(f"\n\U0001f4a1 <i>{readiness.reason_uz}</i>")
    return "\n".join(lines)


# ── Internal helpers ────────────────────────────────────────────────────────


def _build_tactic_result(
    tactic: str,
    reason_uz: str,
    confidence: float,
) -> ClosingTacticResult:
    return ClosingTacticResult(
        tactic=tactic,
        tactic_uz=TACTIC_LABELS.get(tactic, tactic),
        reason_uz=reason_uz,
        suggested_message_uz=_TACTIC_MESSAGES.get(tactic, ""),
        confidence=confidence,
        fallback_message_uz=_TACTIC_FALLBACKS.get(tactic, ""),
    )


def _build_reason(signals: list[str], blockers: list[str]) -> str:
    """Build English machine-readable reason."""
    parts = []
    if "phone_captured" in signals and "very_high_score" in signals:
        parts.append("hot lead with phone and strong interest")
    elif "phone_captured" in signals:
        parts.append("phone captured")
    if "objection_resolved" in signals:
        parts.append("objection resolved")
    if "high_deal_probability" in signals:
        parts.append("high deal probability")
    if any(b.startswith("unresolved_") for b in blockers):
        parts.append("unresolved objection")
    if "no_phone" in blockers:
        parts.append("no phone yet")
    return "; ".join(parts) if parts else "standard assessment"


def _build_reason_uz(
    tier: str,
    signals: list[str],
    blockers: list[str],
) -> str:
    """Build Uzbek reason for admin card."""
    if tier == TIER_READY_TO_CLOSE:
        if "objection_resolved" in signals:
            return "Lid tayyor \u2014 e'tiroz hal qilingan, hozir yoping!"
        if "very_high_score" in signals:
            return "Juda kuchli qiziqish \u2014 hoziroq harakat qiling!"
        return "Lid yopishga tayyor \u2014 tezda bog'laning!"
    if tier == TIER_NEAR_CLOSE:
        if any(b.startswith("unresolved_") for b in blockers):
            return "Lid yaqin, lekin e'tirozni hal qilish kerak"
        if "no_phone" in blockers:
            return "Lid yaqin \u2014 telefon olishga harakat qiling"
        return "Lid yaqinlashmoqda \u2014 davom eting"
    # NOT_READY
    if "no_phone" in blockers and "poor_conversation_health" in blockers:
        return "Telefon va suhbat sifati past \u2014 avval ishonch o'rnating"
    return "Lid hali tayyor emas \u2014 nurturingda davom eting"
