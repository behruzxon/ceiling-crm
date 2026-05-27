"""
core.services.next_best_action_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AI Sales Autopilot — determines the next best action for each lead,
detects high-conversion opportunities, flags at-risk leads, suggests
closing tactics, and identifies pipeline bottlenecks.

Pure deterministic functions — no I/O, fully testable.

Usage::

    from core.services.next_best_action_service import (
        determine_next_best_action,
        detect_opportunity,
        detect_at_risk,
        suggest_closing_tactic,
        analyze_pipeline_bottlenecks,
    )

    nba = determine_next_best_action(score=72, health_score=68, ...)
    # nba.action == "schedule_measurement"
    # nba.priority == "high"
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.services.signal_vector_service import SignalVector


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NextBestAction:
    """Recommended next action for a lead."""

    action: str
    """Machine-readable action key."""

    priority: str
    """'high' | 'medium' | 'low'."""

    reason: str
    """Short English reason (for logging)."""

    reason_uz: str
    """Uzbek reason for admin card."""

    suggested_message_uz: str
    """Ready-to-send Uzbek message for the manager."""

    confidence: float
    """0.0–1.0 confidence in this recommendation."""


@dataclass(frozen=True, slots=True)
class OpportunityAlert:
    """High-conversion opportunity detected."""

    detected: bool
    score: int
    health_score: int
    recommended_action: str
    recommended_action_uz: str
    reason_uz: str
    opportunity_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AtRiskAlert:
    """Lead at risk of being lost."""

    detected: bool
    risk_reason: str
    risk_reason_uz: str
    recommended_action: str
    recommended_action_uz: str
    urgency: str
    """'immediate' | 'soon' | 'monitor'."""
    risk_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ClosingTactic:
    """Smart deal-closing suggestion."""

    should_close: bool
    tactic: str
    """'urgency_close' | 'bonus_installation' | 'quick_scheduling' | 'limited_offer'."""

    reason_uz: str
    suggested_message_uz: str
    confidence: float


@dataclass(frozen=True, slots=True)
class PipelineInsight:
    """Pipeline stage bottleneck."""

    bottleneck_stage: str
    leads_stuck: int
    recommendation_uz: str


# ── Action catalogue ────────────────────────────────────────────────────────

ACTION_LABELS: dict[str, str] = {
    "schedule_measurement": "Bepul o'lchov taklif qilish",
    "send_discount_offer": "Chegirma taklif qilish",
    "propose_cheaper_option": "Arzon variant taklif qilish",
    "escalate_to_manager": "Menejerga uzatish",
    "send_followup_question": "Savol bilan follow-up",
    "close_deal_attempt": "Bitimni yopish urinishi",
    "send_catalog": "Katalog yuborish",
    "reactivation": "Qayta faollashtirish",
    "wait": "Kutish",
}

_SUGGESTED_MESSAGES: dict[str, str] = {
    "schedule_measurement": ("Ustamiz bepul o'lchov qilib bera oladi. Qaysi vaqt sizga qulay?"),
    "send_discount_offer": ("Sizga maxsus chegirma taklif qilamiz! Tafsilotlar uchun yozing."),
    "propose_cheaper_option": ("Byudjetga mos variant bor \u2014 ko'rsatib beraymi?"),
    "escalate_to_manager": ("Menejer siz bilan bog'lanadi."),
    "send_followup_question": ("Potolok haqida savolingiz bormi? Yordam berishga tayyorman!"),
    "close_deal_attempt": ("Buyurtma berish uchun tayyor bo'lsangiz, hoziroq rasmiylashtiramiz!"),
    "send_catalog": ("Katalogimizni ko'rib chiqing \u2014 qaysi dizayn yoqdi?"),
    "reactivation": ("Salom! Potolok haqida o'yladingizmi? Yangi dizaynlar qo'shildi \U0001f60a"),
    "wait": "",
}

# Closing tactic messages
_CLOSING_MESSAGES: dict[str, str] = {
    "urgency_close": "Bu oy oxirigacha maxsus narx amal qiladi!",
    "bonus_installation": "Buyurtma qilsangiz, bepul o'rnatish xizmati!",
    "quick_scheduling": ("Ertaga ustamiz bepul o'lchab berishi mumkin \u2014 qulayimi?"),
    "limited_offer": "Faqat bugun \u2014 10% chegirma! O'tkazib yubormang!",
}

CLOSING_TACTIC_LABELS: dict[str, str] = {
    "urgency_close": "Shoshilinch taklif",
    "bonus_installation": "Bepul o'rnatish bonusi",
    "quick_scheduling": "Tez rejalashtirish",
    "limited_offer": "Cheklangan taklif",
}

# Pipeline stage order for bottleneck analysis
_STAGE_ORDER = [
    "NEW",
    "PACKAGE_SELECTED",
    "CONTACTED",
    "MEASUREMENT",
    "QUOTE",
    "DEAL",
    "INSTALLATION",
    "COMPLETED",
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

_BOTTLENECK_ADVICE: dict[str, str] = {
    "NEW": "Yangi lidlarga tezroq bog'laning \u2014 dastlabki 10 daqiqa hal qiluvchi",
    "PACKAGE_SELECTED": "Paket tanlagan lidlarga o'lchov taklif qiling",
    "CONTACTED": "O'lchov yoki narx taklif qilib bosqichni ilgari surting",
    "MEASUREMENT": "O'lchov natijasi bo'yicha narx taklif yuboring",
    "QUOTE": "Narx tushuntirish yoki taqqoslash taklif qiling",
    "DEAL": "O'rnatish sanasini rejalashtiring",
    "INSTALLATION": "O'rnatish holatini yangilang",
}


# ── Next Best Action Engine ─────────────────────────────────────────────────


def determine_next_best_action(
    *,
    score: int = 0,
    health_score: int = 50,
    last_objection: str | None = None,
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
) -> NextBestAction:
    """Determine the single best next action for this lead.

    All parameters keyword-only with safe defaults. Pure function.
    When *signal_vector* is provided, values are extracted from it.
    """
    if signal_vector is not None:
        sv = signal_vector
        score = sv.lead_score_raw
        health_score = sv.health_score_raw
        last_objection = sv.last_objection
        objection_resolved = sv.objection_resolved
        minutes_since_last_activity = sv.minutes_since_last_activity
        current_stage = sv.current_stage
        phone_captured = sv.phone_captured
        area_m2 = sv.area_m2
        follow_up_count = sv.follow_up_count
        closing_confidence = sv.closing_confidence_raw
        lead_temperature = sv.lead_temperature
        buyer_type = sv.buyer_type
        closing_attempted = sv.closing_attempted
        deal_probability_percent = sv.deal_probability_percent

    conf = closing_confidence or 0.0
    dp = deal_probability_percent or 0
    temp = (lead_temperature or "").lower()
    stage = (current_stage or "NEW").upper()
    is_hot = temp == "hot" or score >= 60

    # ── Rule 1: Close-ready lead → close_deal_attempt (high) ──────
    if dp >= 70 and phone_captured:
        return NextBestAction(
            action="close_deal_attempt",
            priority="high",
            reason="high deal probability with phone",
            reason_uz="Yuqori ehtimollik va telefon mavjud",
            suggested_message_uz=_SUGGESTED_MESSAGES["close_deal_attempt"],
            confidence=min(1.0, dp / 100 + 0.1),
        )

    # ── Rule 2: HOT lead with data → schedule_measurement (high) ──
    if is_hot and phone_captured and area_m2 is not None:
        return NextBestAction(
            action="schedule_measurement",
            priority="high",
            reason="hot lead with phone and area",
            reason_uz="HOT lid \u2014 telefon va maydon ma'lum",
            suggested_message_uz=_SUGGESTED_MESSAGES["schedule_measurement"],
            confidence=0.85,
        )

    # ── Rule 3: Critical health + decent score → escalate (high) ──
    if health_score <= 30 and score >= 40:
        return NextBestAction(
            action="escalate_to_manager",
            priority="high",
            reason="critical health but engaged lead",
            reason_uz="Kritik holat, lekin lid faol \u2014 menejer kerak",
            suggested_message_uz=_SUGGESTED_MESSAGES["escalate_to_manager"],
            confidence=0.80,
        )

    # ── Rule 4: Price objection unresolved → cheaper/discount ─────
    if last_objection in ("expensive", "compare") and not objection_resolved:
        if buyer_type == "price_sensitive":
            return NextBestAction(
                action="propose_cheaper_option",
                priority="high",
                reason="price objection on price-sensitive buyer",
                reason_uz="Narx e'tirozi \u2014 arzon variant taklif qiling",
                suggested_message_uz=_SUGGESTED_MESSAGES["propose_cheaper_option"],
                confidence=0.75,
            )
        return NextBestAction(
            action="send_discount_offer",
            priority="high",
            reason="price objection unresolved",
            reason_uz="Narx e'tirozi hal qilinmagan \u2014 chegirma taklif",
            suggested_message_uz=_SUGGESTED_MESSAGES["send_discount_offer"],
            confidence=0.70,
        )

    # ── Rule 5: HOT lead with phone only → close attempt (high) ──
    if is_hot and phone_captured and not closing_attempted:
        return NextBestAction(
            action="close_deal_attempt",
            priority="high",
            reason="hot lead with phone, not yet attempted close",
            reason_uz="HOT lid, hali yopish urinilmagan",
            suggested_message_uz=_SUGGESTED_MESSAGES["close_deal_attempt"],
            confidence=0.70,
        )

    # ── Rule 6: Good score + confidence → close attempt (medium) ──
    if score >= 50 and conf >= 0.5 and not closing_attempted:
        return NextBestAction(
            action="close_deal_attempt",
            priority="medium",
            reason="good score and confidence, not yet closed",
            reason_uz="Yaxshi ball va ishonch \u2014 yopish vaqti",
            suggested_message_uz=_SUGGESTED_MESSAGES["close_deal_attempt"],
            confidence=0.60,
        )

    # ── Rule 7: Missing data → ask questions (medium) ────────────
    if score >= 30 and area_m2 is None:
        return NextBestAction(
            action="send_followup_question",
            priority="medium",
            reason="engaged but missing area data",
            reason_uz="Faol lid \u2014 maydon haqida so'rang",
            suggested_message_uz=(
                "Xonangiz taxminan nechchi m\u00b2? " "Aniq narx hisoblab berishimiz uchun kerak."
            ),
            confidence=0.55,
        )

    if score >= 30 and not phone_captured:
        return NextBestAction(
            action="send_catalog",
            priority="medium",
            reason="engaged but no phone",
            reason_uz="Faol lid \u2014 katalog orqali jalb qiling",
            suggested_message_uz=_SUGGESTED_MESSAGES["send_catalog"],
            confidence=0.50,
        )

    # ── Rule 8: Long silence → reactivation or follow-up ─────────
    if minutes_since_last_activity >= 1440:  # 24h+
        return NextBestAction(
            action="reactivation",
            priority="medium",
            reason="inactive for 24h+",
            reason_uz="24+ soat javob yo'q \u2014 qayta faollashtirish",
            suggested_message_uz=_SUGGESTED_MESSAGES["reactivation"],
            confidence=0.45,
        )

    if minutes_since_last_activity >= 180 and is_hot:  # 3h for HOT
        return NextBestAction(
            action="send_followup_question",
            priority="medium",
            reason="hot lead silent for 3h+",
            reason_uz="HOT lid 3+ soat javobsiz",
            suggested_message_uz=_SUGGESTED_MESSAGES["send_followup_question"],
            confidence=0.55,
        )

    if minutes_since_last_activity >= 360:  # 6h for any
        return NextBestAction(
            action="send_followup_question",
            priority="low",
            reason="lead silent for 6h+",
            reason_uz="Lid 6+ soat javobsiz",
            suggested_message_uz=_SUGGESTED_MESSAGES["send_followup_question"],
            confidence=0.40,
        )

    # ── Rule 9: Follow-up fatigue → wait ─────────────────────────
    if follow_up_count >= 4:
        return NextBestAction(
            action="wait",
            priority="low",
            reason="follow-up fatigue, let lead rest",
            reason_uz="Ko'p follow-up \u2014 kutish kerak",
            suggested_message_uz="",
            confidence=0.60,
        )

    # ── Default: soft follow-up (low) ────────────────────────────
    return NextBestAction(
        action="send_followup_question",
        priority="low",
        reason="default soft follow-up",
        reason_uz="Yumshoq follow-up tavsiya etiladi",
        suggested_message_uz=_SUGGESTED_MESSAGES["send_followup_question"],
        confidence=0.35,
    )


# ── Opportunity Detector ────────────────────────────────────────────────────


def detect_opportunity(
    *,
    score: int = 0,
    health_score: int = 50,
    last_objection: str | None = None,
    objection_resolved: bool = False,
    minutes_since_last_activity: int = 0,
    phone_captured: bool = False,
    area_m2: float | None = None,
    closing_confidence: float | None = None,
    deal_probability_percent: int | None = None,
    signal_vector: SignalVector | None = None,
) -> OpportunityAlert:
    """Detect if a lead is a high-conversion opportunity.

    Conditions: score>70, health>65, objection resolved or absent,
    last message within 1h, phone captured.
    When *signal_vector* is provided, values are extracted from it.
    """
    if signal_vector is not None:
        sv = signal_vector
        score = sv.lead_score_raw
        health_score = sv.health_score_raw
        last_objection = sv.last_objection
        objection_resolved = sv.objection_resolved
        minutes_since_last_activity = sv.minutes_since_last_activity
        phone_captured = sv.phone_captured
        area_m2 = sv.area_m2
        closing_confidence = sv.closing_confidence_raw
        deal_probability_percent = sv.deal_probability_percent

    signals: list[str] = []
    detected = True

    # Score check
    if score > 70:
        signals.append("high_score")
    elif score > 50:
        signals.append("good_score")
    else:
        detected = False

    # Health check
    if health_score > 65:
        signals.append("healthy_conversation")
    elif health_score > 50:
        signals.append("decent_health")
    else:
        detected = False

    # Objection check
    if last_objection and not objection_resolved:
        detected = False
    elif last_objection and objection_resolved:
        signals.append("objection_resolved")
    else:
        signals.append("no_objection")

    # Recency check
    if minutes_since_last_activity <= 60:
        signals.append("recent_activity")
    elif minutes_since_last_activity <= 180:
        signals.append("somewhat_recent")
    else:
        detected = False

    # Phone is strongly preferred
    if phone_captured:
        signals.append("phone_captured")

    # Extra boost: deal probability
    dp = deal_probability_percent or 0
    if dp >= 60:
        signals.append("high_probability")
        # Can override missing criteria if probability is very high
        if dp >= 80 and score > 50 and phone_captured:
            detected = True

    # Pick action
    if phone_captured and area_m2 is not None:
        action = "schedule_measurement"
        action_uz = "Bepul o'lchov taklif qiling"
    elif phone_captured:
        action = "close_deal_attempt"
        action_uz = "Bitimni yopishga harakat qiling"
    else:
        action = "send_followup_question"
        action_uz = "Ma'lumot so'rang va qo'ng'iroq taklif qiling"

    return OpportunityAlert(
        detected=detected,
        score=score,
        health_score=health_score,
        recommended_action=action,
        recommended_action_uz=action_uz,
        reason_uz=(
            "Yuqori ball, sog'lom suhbat, faol lid"
            if detected
            else "Opportunity shartlari bajarilmagan"
        ),
        opportunity_signals=signals,
    )


# ── Lost Lead Prevention ───────────────────────────────────────────────────


def detect_at_risk(
    *,
    score: int = 0,
    health_score: int = 50,
    last_objection: str | None = None,
    objection_resolved: bool = False,
    minutes_since_last_activity: int = 0,
    lead_temperature: str | None = None,
    follow_up_count: int = 0,
    closing_confidence: float | None = None,
    current_stage: str | None = None,
    signal_vector: SignalVector | None = None,
) -> AtRiskAlert:
    """Detect if a lead is at risk of being lost.

    When *signal_vector* is provided, values are extracted from it.
    """
    if signal_vector is not None:
        sv = signal_vector
        score = sv.lead_score_raw
        health_score = sv.health_score_raw
        last_objection = sv.last_objection
        objection_resolved = sv.objection_resolved
        minutes_since_last_activity = sv.minutes_since_last_activity
        lead_temperature = sv.lead_temperature
        follow_up_count = sv.follow_up_count
        closing_confidence = sv.closing_confidence_raw
        current_stage = sv.current_stage

    signals: list[str] = []
    detected = False
    urgency = "monitor"
    temp = (lead_temperature or "").lower()
    conf = closing_confidence or 0.0

    # ── HOT lead going cold ──────────────────────────────────────
    if temp == "hot" and minutes_since_last_activity >= 180:
        detected = True
        urgency = "immediate"
        signals.append("hot_lead_inactive_3h")

    # ── Unresolved objection + low health ────────────────────────
    if last_objection and not objection_resolved and health_score < 45:
        detected = True
        if urgency != "immediate":
            urgency = "soon"
        signals.append("unresolved_objection_low_health")

    # ── Health critical on engaged lead ──────────────────────────
    if health_score <= 30 and score >= 30:
        detected = True
        if urgency != "immediate":
            urgency = "soon"
        signals.append("critical_health_engaged")

    # ── Follow-up fatigue with no progress ────────────────────────
    stage = (current_stage or "NEW").upper()
    if follow_up_count >= 4 and stage in ("NEW", "PACKAGE_SELECTED", "CONTACTED"):
        detected = True
        signals.append("followup_fatigue_no_progress")

    # ── Warm lead long silence ───────────────────────────────────
    if temp == "warm" and minutes_since_last_activity >= 360:
        detected = True
        signals.append("warm_lead_inactive_6h")

    # ── Low confidence on advanced stage ─────────────────────────
    if conf < 0.2 and stage in ("QUOTE", "DEAL") and score >= 30:
        detected = True
        signals.append("low_confidence_advanced_stage")

    # Pick recommended action
    if "hot_lead_inactive_3h" in signals:
        action = "send_followup_question"
        action_uz = "Darhol follow-up yuboring"
    elif "unresolved_objection_low_health" in signals:
        if last_objection in ("expensive", "compare"):
            action = "propose_cheaper_option"
            action_uz = "Arzon variant taklif qiling"
        else:
            action = "escalate_to_manager"
            action_uz = "Menejerga uzating"
    elif "critical_health_engaged" in signals:
        action = "escalate_to_manager"
        action_uz = "Menejerga uzating \u2014 lid kritik holatda"
    elif "followup_fatigue_no_progress" in signals:
        action = "escalate_to_manager"
        action_uz = "Menejer jalb qiling \u2014 ko'p follow-up, natija yo'q"
    else:
        action = "send_followup_question"
        action_uz = "Yumshoq follow-up yuboring"

    # Build risk reason
    reasons = []
    if last_objection and not objection_resolved:
        _obj_uz = {
            "expensive": "narx e'tirozi",
            "compare": "taqqoslash",
            "delay": "kechiktirish",
            "trust": "ishonch muammosi",
            "angry": "norozilik",
        }
        reasons.append(_obj_uz.get(last_objection, last_objection))
    if minutes_since_last_activity >= 180:
        hours = minutes_since_last_activity // 60
        reasons.append(f"{hours}+ soat javobsiz")
    if health_score <= 30:
        reasons.append("kritik suhbat holati")
    if follow_up_count >= 4:
        reasons.append(f"{follow_up_count} ta follow-up")

    reason_uz = " + ".join(reasons) if reasons else "Xavf belgilari aniqlangan"

    return AtRiskAlert(
        detected=detected,
        risk_reason=" + ".join(signals) if signals else "none",
        risk_reason_uz=reason_uz,
        recommended_action=action,
        recommended_action_uz=action_uz,
        urgency=urgency,
        risk_signals=signals,
    )


# ── Smart Deal Closing Assistant ────────────────────────────────────────────


def suggest_closing_tactic(
    *,
    score: int = 0,
    phone_captured: bool = False,
    area_m2: float | None = None,
    closing_confidence: float | None = None,
    deal_probability_percent: int | None = None,
    buyer_type: str | None = None,
    lead_temperature: str | None = None,
    last_objection: str | None = None,
    closing_attempted: bool = False,
    signal_vector: SignalVector | None = None,
) -> ClosingTactic:
    """Suggest a closing tactic when the lead is close to conversion.

    When *signal_vector* is provided, values are extracted from it.
    """
    if signal_vector is not None:
        sv = signal_vector
        score = sv.lead_score_raw
        phone_captured = sv.phone_captured
        area_m2 = sv.area_m2
        closing_confidence = sv.closing_confidence_raw
        deal_probability_percent = sv.deal_probability_percent
        buyer_type = sv.buyer_type
        lead_temperature = sv.lead_temperature
        last_objection = sv.last_objection
        closing_attempted = sv.closing_attempted

    dp = deal_probability_percent or 0
    conf = closing_confidence or 0.0
    temp = (lead_temperature or "").lower()

    # Check if closing should be attempted
    should_close = (
        (dp >= 60)
        or (score >= 60 and phone_captured)
        or (conf >= 0.6 and phone_captured)
        or (temp == "hot" and phone_captured and score >= 40)
    )

    if not should_close:
        return ClosingTactic(
            should_close=False,
            tactic="none",
            reason_uz="Yopish uchun hali erta",
            suggested_message_uz="",
            confidence=0.0,
        )

    # Select tactic based on buyer type and context
    if buyer_type == "fast_buyer":
        tactic = "quick_scheduling"
        reason = "Tez qaror xaridor \u2014 o'lchov rejalashtiring"
        tactic_conf = 0.80
    elif buyer_type == "price_sensitive" or last_objection == "expensive":
        tactic = "limited_offer"
        reason = "Narxga sezgir \u2014 cheklangan taklif bering"
        tactic_conf = 0.70
    elif area_m2 is not None and area_m2 >= 20:
        tactic = "bonus_installation"
        reason = "Katta maydon \u2014 bepul o'rnatish bonusi"
        tactic_conf = 0.75
    elif dp >= 80 or conf >= 0.8:
        tactic = "urgency_close"
        reason = "Juda yuqori ehtimollik \u2014 shoshilinch yoping"
        tactic_conf = 0.85
    elif closing_attempted:
        # Already tried once, use different approach
        tactic = "limited_offer"
        reason = "Oldingi urinish bo'lgan \u2014 cheklangan taklif"
        tactic_conf = 0.65
    else:
        tactic = "urgency_close"
        reason = "HOT lid \u2014 shoshilinch taklif yuboring"
        tactic_conf = 0.70

    return ClosingTactic(
        should_close=True,
        tactic=tactic,
        reason_uz=reason,
        suggested_message_uz=_CLOSING_MESSAGES[tactic],
        confidence=tactic_conf,
    )


# ── Pipeline Bottleneck Analysis ────────────────────────────────────────────


def analyze_pipeline_bottlenecks(
    stage_counts: dict[str, int],
    *,
    min_stuck: int = 3,
) -> list[PipelineInsight]:
    """Identify pipeline stages where leads are accumulating.

    *stage_counts*: ``{"NEW": 30, "CONTACTED": 12, ...}``
    Returns insights sorted by severity (most stuck first).
    """
    if not stage_counts:
        return []

    insights: list[PipelineInsight] = []
    total = sum(stage_counts.values()) or 1

    # Find stages with disproportionate lead counts
    for stage in _STAGE_ORDER:
        count = stage_counts.get(stage, 0)
        if count < min_stuck:
            continue

        # Check if this stage has more leads than the next stage
        idx = _STAGE_ORDER.index(stage)
        if idx < len(_STAGE_ORDER) - 1:
            next_count = stage_counts.get(_STAGE_ORDER[idx + 1], 0)
            ratio = count / max(next_count, 1)

            if ratio >= 2.0 and count >= min_stuck:
                advice = _BOTTLENECK_ADVICE.get(
                    stage,
                    f"{_STAGE_LABELS.get(stage, stage)} bosqichini tezlashtiring",
                )
                insights.append(
                    PipelineInsight(
                        bottleneck_stage=stage,
                        leads_stuck=count,
                        recommendation_uz=advice,
                    )
                )

    # Also flag any stage with >30% of all leads
    for stage in _STAGE_ORDER:
        count = stage_counts.get(stage, 0)
        if count / total > 0.30 and count >= min_stuck:
            # Check if already flagged
            if not any(i.bottleneck_stage == stage for i in insights):
                advice = _BOTTLENECK_ADVICE.get(
                    stage,
                    f"{_STAGE_LABELS.get(stage, stage)} bosqichida lid to'planmoqda",
                )
                insights.append(
                    PipelineInsight(
                        bottleneck_stage=stage,
                        leads_stuck=count,
                        recommendation_uz=advice,
                    )
                )

    insights.sort(key=lambda x: x.leads_stuck, reverse=True)
    return insights[:3]


# ── HTML Alert Builders ─────────────────────────────────────────────────────


def build_opportunity_alert_text(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    score: int,
    health_score: int,
    recommended_action_uz: str,
) -> str:
    """Build HTML alert for high-conversion opportunity."""
    return (
        "\U0001f525 <b>High Conversion Opportunity</b>\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\u2b50 Score: {score}\n"
        f"\U0001f3e5 Health: {health_score}/100\n\n"
        f"<b>Tavsiya:</b> {recommended_action_uz}"
    )


def build_at_risk_alert_text(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    risk_reason_uz: str,
    recommended_action_uz: str,
    urgency: str,
) -> str:
    """Build HTML alert for at-risk lead."""
    _urgency_badges = {
        "immediate": "\U0001f534",
        "soon": "\U0001f7e1",
        "monitor": "\U0001f7e2",
    }
    badge = _urgency_badges.get(urgency, "\u26aa")
    return (
        f"\u26a0\ufe0f <b>Lead At Risk</b> {badge}\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\u26a0\ufe0f Sabab: {risk_reason_uz}\n\n"
        f"<b>Tavsiya:</b> {recommended_action_uz}"
    )


def build_autopilot_suggestion_text(
    *,
    lead_id: int,
    lead_name: str,
    action_uz: str,
    reason_uz: str,
    suggested_message_uz: str,
    priority: str,
) -> str:
    """Build autopilot suggestion card for admin."""
    _prio_badges = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}
    badge = _prio_badges.get(priority, "\u26aa")
    lines = [
        f"\U0001f916 <b>Sales Autopilot Suggestion</b> {badge}\n",
        f"\U0001f4cb Lead: #{lead_id} \u2014 {lead_name}",
        f"\U0001f3af Amal: {action_uz}",
        f"\U0001f4a1 Sabab: {reason_uz}",
    ]
    if suggested_message_uz:
        lines.append("\n\U0001f4ac <b>Taklif qilinadigan xabar:</b>")
        lines.append(f"<code>{suggested_message_uz}</code>")
    return "\n".join(lines)


def build_closing_alert_text(
    *,
    lead_id: int,
    lead_name: str,
    tactic_uz: str,
    reason_uz: str,
    suggested_message_uz: str,
) -> str:
    """Build deal-closing opportunity alert for admin."""
    return (
        f"\U0001f3af <b>Deal Closing Opportunity</b>\n\n"
        f"\U0001f4cb Lead: #{lead_id} \u2014 {lead_name}\n"
        f"\U0001f3c6 Taktika: {tactic_uz}\n"
        f"\U0001f4a1 Sabab: {reason_uz}\n\n"
        f"\U0001f4ac <b>Taklif:</b>\n"
        f"<code>{suggested_message_uz}</code>"
    )


def build_pipeline_insight_text(
    insights: list[PipelineInsight],
) -> str:
    """Build pipeline bottleneck insight card."""
    if not insights:
        return ""
    lines = ["\U0001f4ca <b>Pipeline Insight</b>\n"]
    for ins in insights:
        label = _STAGE_LABELS.get(ins.bottleneck_stage, ins.bottleneck_stage)
        lines.append(f"\u26a0\ufe0f <b>{label}</b>: {ins.leads_stuck} lid to'planmoqda")
        lines.append(f"   \U0001f4a1 {ins.recommendation_uz}")
    return "\n".join(lines)


# ── Batch utility for autopilot job ─────────────────────────────────────────


def compute_autopilot_metrics(
    leads_data: list[dict],
) -> dict:
    """Compute aggregate autopilot metrics from enriched lead dicts.

    Expects optional keys: ``nba_action``, ``nba_priority``,
    ``opportunity_detected``, ``at_risk_detected``, ``closing_ready``.
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

    action_distribution = [{"action": a, "count": c} for a, c in action_counter.most_common(6)]

    return {
        "action_distribution": action_distribution,
        "opportunity_count": opportunity_count,
        "at_risk_count": at_risk_count,
        "closing_ready_count": closing_ready_count,
    }
