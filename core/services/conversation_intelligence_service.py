"""
core.services.conversation_intelligence_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rule-based conversation intelligence: health scoring, signal detection,
risk classification, manager response monitoring, and follow-up suggestions.

Pure deterministic functions — no I/O, fully testable.

Usage::

    from core.services.conversation_intelligence_service import (
        analyze_conversation,
        assess_manager_response,
    )

    result = analyze_conversation(
        score=55,
        last_objection="expensive",
        last_objection_severity="medium",
        phone_captured=True,
        area_m2=18.0,
        minutes_since_last_activity=45,
        follow_up_count=1,
        lead_temperature="warm",
        closing_confidence=0.5,
        buyer_type="price_sensitive",
        last_negotiation_tactic="cheaper_alternative",
        has_district=True,
    )
    # result.health_score == 68
    # result.signals == ["interest", "price_resistance"]
    # result.risk_level == "medium"
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationIntelligence:
    """Full conversation analysis result."""

    health_score: int
    """0-100 composite health score."""

    signals: list[str]
    """Detected signals: interest, hesitation, confusion, price_resistance,
    silence_risk, strong_intent, cooling, engaged, objection_unresolved."""

    risk_level: str
    """'low' | 'medium' | 'high' | 'critical'."""

    recommended_action: str
    """Machine-readable action key."""

    recommended_action_uz: str
    """Uzbek-language sales-safe suggestion for admin."""

    quality_score: int
    """0-100 conversation quality score (engagement + progress)."""

    cooling_detected: bool
    """True if lead is cooling down (activity drop)."""

    silence_minutes: int
    """Minutes since last activity."""

    risk_reasons: list[str] = field(default_factory=list)
    """Human-readable risk reasons (Uzbek)."""


@dataclass(frozen=True, slots=True)
class ManagerResponseAssessment:
    """Manager response delay assessment."""

    is_delayed: bool
    """True if response exceeds threshold."""

    delay_minutes: int
    """Minutes since last user message without manager reply."""

    severity: str
    """'ok' | 'warning' | 'critical'."""

    alert_text: str
    """Pre-formatted alert text for admin (HTML). Empty if ok."""


# ── Signal keywords (Uzbek + Russian) ──────────────────────────────────────

_INTEREST_SIGNALS: frozenset[str] = frozenset({
    "qachon", "o'lchov", "buyurtma", "narx", "hisob",
    "qancha", "bepul", "kelasizmi", "tayyor", "boshlaymiz",
    "когда", "замер", "заказ", "цена", "сколько",
})

_HESITATION_SIGNALS: frozenset[str] = frozenset({
    "o'ylab", "fikrlab", "keyinroq", "keyin", "bilmayman",
    "aniq emas", "qiyin", "ko'raman", "maslahat",
    "подумаю", "позже", "не знаю", "не уверен",
})

_CONFUSION_SIGNALS: frozenset[str] = frozenset({
    "tushunmadim", "nima degani", "qanday bo'ladi",
    "nimani nazarda", "qaysi", "farqi nima",
    "не понял", "не понимаю", "как это", "что значит",
})


# ── Action suggestions (Uzbek, sales-safe) ─────────────────────────────────

_ACTION_SUGGESTIONS: dict[str, str] = {
    "schedule_measurement": (
        "Bepul o'lchov taklif qiling — "
        "\"Qaysi kun qulay? Mutaxassisimiz bepul o'lchab beradi.\""
    ),
    "offer_discount": (
        "Arzonroq variant yoki chegirma taklif qiling — "
        "\"Sizga mos byudjet variant bor, hisoblab beraman.\""
    ),
    "ask_clarification": (
        "Aniqlashtiruvchi savol bering — "
        "\"Qaysi xona uchun kerak? Taxminan nechchi m²?\""
    ),
    "escalate_manager": (
        "Menejerga uzating — lid shaxsiy yondashuvni talab qiladi."
    ),
    "send_catalog": (
        "Katalog yuboring — \"Bizning ishlarimiz fotosi — "
        "qaysi dizayn yoqdi?\""
    ),
    "soft_followup": (
        "Yumshoq eslatma yuboring — "
        "\"Salom! Potolok haqida savolingiz bormi? Yordam berishga tayyorman 🙂\""
    ),
    "urgency_offer": (
        "Shoshilinch taklif yuboring — "
        "\"Bu oy oxirigacha maxsus narx amal qilmoqda!\""
    ),
    "reactivation": (
        "Qayta faollashtirish — "
        "\"Salom! Potolok haqida o'yladingizmi? Yangi dizaynlar qo'shildi 🙂\""
    ),
    "wait": "Kutish — lid hozircha faol, aralashish shart emas.",
    "no_action": "Hozircha amaliyot kerak emas.",
}


# ── Risk level thresholds ──────────────────────────────────────────────────

_RISK_THRESHOLDS = {
    "critical": 30,   # health_score <= 30
    "high": 50,       # health_score <= 50
    "medium": 70,     # health_score <= 70
}

# Manager response thresholds (minutes)
_MANAGER_DELAY_WARNING = 10   # HOT lead
_MANAGER_DELAY_CRITICAL = 20  # any lead
_MANAGER_DELAY_WARM = 30      # WARM lead threshold

# Silence/cooling thresholds (minutes) — business hours
_SILENCE_HOT = 120     # 2 hours
_SILENCE_WARM = 360    # 6 hours
_SILENCE_COLD = 1440   # 24 hours

# Silence/cooling thresholds — off-hours (relaxed to avoid false alarms)
_SILENCE_HOT_OFF = 360    # 6 hours
_SILENCE_WARM_OFF = 720   # 12 hours
_SILENCE_COLD_OFF = 2160  # 36 hours


# ── Main analyzer ──────────────────────────────────────────────────────────


def analyze_conversation(
    *,
    score: int = 0,
    last_objection: str | None = None,
    last_objection_severity: str | None = None,
    last_user_message: str | None = None,
    phone_captured: bool = False,
    area_m2: float | None = None,
    minutes_since_last_activity: int = 0,
    follow_up_count: int = 0,
    lead_temperature: str | None = None,
    closing_confidence: float | None = None,
    buyer_type: str | None = None,
    last_negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    has_district: bool = False,
    last_closing_attempt: str | None = None,
    lead_status: str | None = None,
    current_stage: str | None = None,
) -> ConversationIntelligence:
    """Analyze conversation signals and compute health score.

    All parameters keyword-only with safe defaults. Pure function.
    """
    signals: list[str] = []
    risk_reasons: list[str] = []
    health = 50  # base score

    # ── Detect text-based signals ──────────────────────────────────
    if last_user_message:
        lower = last_user_message.lower()
        if any(kw in lower for kw in _INTEREST_SIGNALS):
            signals.append("interest")
            health += 10
        if any(kw in lower for kw in _HESITATION_SIGNALS):
            signals.append("hesitation")
            health -= 8
            risk_reasons.append("Xaridor ikkilanmoqda")
        if any(kw in lower for kw in _CONFUSION_SIGNALS):
            signals.append("confusion")
            health -= 5
            risk_reasons.append("Xaridor tushunmagan")

    # ── Score-based signals ────────────────────────────────────────
    if score >= 60:
        signals.append("strong_intent")
        health += 15
    elif score >= 40:
        signals.append("engaged")
        health += 8
    elif score < 15:
        health -= 10
        risk_reasons.append("Juda past qiziqish bali")

    # ── Objection signals ──────────────────────────────────────────
    if last_objection in ("expensive", "compare"):
        signals.append("price_resistance")
        severity_penalty = {"low": -3, "medium": -8, "high": -15}
        health += severity_penalty.get(last_objection_severity or "low", -3)
        if last_objection_severity == "high":
            risk_reasons.append("Kuchli narx e'tirozi")

    if last_objection and last_negotiation_tactic is None:
        signals.append("objection_unresolved")
        health -= 7
        risk_reasons.append("E'tiroz hali hal qilinmagan")

    if negotiation_escalated:
        health -= 5
        risk_reasons.append("Muzokara eskalatsiya qilingan")

    # ── Contact info signals ───────────────────────────────────────
    if phone_captured:
        health += 12
    if area_m2 is not None:
        health += 8
    if has_district:
        health += 5

    # ── Confidence signals ─────────────────────────────────────────
    if closing_confidence is not None:
        if closing_confidence >= 0.7:
            health += 10
        elif closing_confidence >= 0.4:
            health += 5
        elif closing_confidence < 0.2:
            health -= 5

    # ── Closing attempt bonus ──────────────────────────────────────
    if last_closing_attempt:
        health += 5

    # ── Follow-up fatigue ──────────────────────────────────────────
    if follow_up_count >= 4:
        health -= 10
        risk_reasons.append("Ko'p follow-up — charchash xavfi")
    elif follow_up_count >= 2:
        health -= 3

    # ── Silence / cooling risk (time-aware thresholds) ─────────────
    cooling = False
    temp = (lead_temperature or "").lower()

    # Use relaxed thresholds during off-hours to avoid false alarms
    try:
        from shared.utils.business_hours import is_off_hours as _is_off
        _off = _is_off()
    except Exception:
        _off = False

    silence_hot = _SILENCE_HOT_OFF if _off else _SILENCE_HOT
    silence_warm = _SILENCE_WARM_OFF if _off else _SILENCE_WARM
    silence_cold = _SILENCE_COLD_OFF if _off else _SILENCE_COLD
    # Stalled conversation threshold: 180min off-hours, 60min business
    stall_threshold = 180 if _off else 60

    if temp == "hot" and minutes_since_last_activity >= silence_hot:
        signals.append("silence_risk")
        cooling = True
        health -= 15
        risk_reasons.append(
            f"HOT lid {minutes_since_last_activity} daqiqa javobsiz"
        )
    elif temp == "warm" and minutes_since_last_activity >= silence_warm:
        signals.append("silence_risk")
        cooling = True
        health -= 10
        risk_reasons.append(
            f"WARM lid {minutes_since_last_activity} daqiqa javobsiz"
        )
    elif minutes_since_last_activity >= silence_cold:
        signals.append("silence_risk")
        cooling = True
        health -= 12
        risk_reasons.append(
            f"Lid {minutes_since_last_activity // 60} soat javobsiz"
        )
    elif minutes_since_last_activity >= stall_threshold:
        health -= 3  # mild penalty

    if cooling:
        signals.append("cooling")

    # ── Pipeline stage bonus ───────────────────────────────────────
    stage = (current_stage or "").upper()
    _STAGE_BONUS = {
        "DEAL": 15, "INSTALLATION": 15, "COMPLETED": 20,
        "QUOTE": 10, "MEASUREMENT": 8, "CONTACTED": 5,
    }
    health += _STAGE_BONUS.get(stage, 0)

    # ── Clamp health score ─────────────────────────────────────────
    health = max(0, min(100, health))

    # ── Quality score (engagement + progress composite) ────────────
    quality = _compute_quality_score(
        score=score,
        phone_captured=phone_captured,
        area_m2=area_m2,
        has_district=has_district,
        follow_up_count=follow_up_count,
        closing_confidence=closing_confidence,
        last_closing_attempt=last_closing_attempt,
        last_objection=last_objection,
        last_negotiation_tactic=last_negotiation_tactic,
        current_stage=stage,
    )

    # ── Risk level ─────────────────────────────────────────────────
    if health <= _RISK_THRESHOLDS["critical"]:
        risk_level = "critical"
    elif health <= _RISK_THRESHOLDS["high"]:
        risk_level = "high"
    elif health <= _RISK_THRESHOLDS["medium"]:
        risk_level = "medium"
    else:
        risk_level = "low"

    # ── Recommended action ─────────────────────────────────────────
    action = _pick_action(
        health=health,
        signals=signals,
        score=score,
        phone_captured=phone_captured,
        area_m2=area_m2,
        buyer_type=buyer_type,
        cooling=cooling,
        follow_up_count=follow_up_count,
        last_objection=last_objection,
        minutes_since_last_activity=minutes_since_last_activity,
    )
    action_uz = _ACTION_SUGGESTIONS.get(action, "")

    return ConversationIntelligence(
        health_score=health,
        signals=signals[:8],
        risk_level=risk_level,
        recommended_action=action,
        recommended_action_uz=action_uz,
        quality_score=quality,
        cooling_detected=cooling,
        silence_minutes=minutes_since_last_activity,
        risk_reasons=risk_reasons[:5],
    )


# ── Manager response assessment ────────────────────────────────────────────


def assess_manager_response(
    *,
    minutes_since_user_message: int,
    lead_temperature: str | None = None,
    score: int = 0,
    lead_id: int = 0,
    lead_name: str = "",
) -> ManagerResponseAssessment:
    """Check if manager response is delayed for this lead.

    Returns structured assessment with pre-formatted alert text.
    """
    temp = (lead_temperature or "").lower()
    is_hot = temp == "hot" or score >= 60

    if is_hot and minutes_since_user_message >= _MANAGER_DELAY_WARNING:
        severity = (
            "critical" if minutes_since_user_message >= _MANAGER_DELAY_CRITICAL
            else "warning"
        )
        alert = (
            f"\u26a0\ufe0f <b>Manager Response Delay</b>\n\n"
            f"\U0001f4cb Lead: #{lead_id}\n"
            f"\U0001f464 {lead_name}\n"
            f"\u23f0 Last message: {minutes_since_user_message} daqiqa oldin\n"
            f"\U0001f525 Temperature: HOT\n\n"
            f"\u26a0\ufe0f Risk: Lead sovib ketmoqda"
        )
        return ManagerResponseAssessment(
            is_delayed=True,
            delay_minutes=minutes_since_user_message,
            severity=severity,
            alert_text=alert,
        )

    is_warm = temp == "warm" or score >= 30
    if is_warm and minutes_since_user_message >= _MANAGER_DELAY_WARM:
        alert = (
            f"\u26a0\ufe0f <b>Manager Response Delay</b>\n\n"
            f"\U0001f4cb Lead: #{lead_id}\n"
            f"\U0001f464 {lead_name}\n"
            f"\u23f0 Last message: {minutes_since_user_message} daqiqa oldin\n"
            f"\U0001f7e1 Temperature: WARM\n\n"
            f"\u26a0\ufe0f Risk: Lead sovib ketishi mumkin"
        )
        return ManagerResponseAssessment(
            is_delayed=True,
            delay_minutes=minutes_since_user_message,
            severity="warning",
            alert_text=alert,
        )

    return ManagerResponseAssessment(
        is_delayed=False,
        delay_minutes=minutes_since_user_message,
        severity="ok",
        alert_text="",
    )


# ── Lead cooling alert builder ─────────────────────────────────────────────


def build_cooling_alert(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    minutes_inactive: int,
    lead_temperature: str,
    recommended_action_uz: str,
) -> str:
    """Build a pre-formatted cooling alert for admin group (HTML)."""
    hours = minutes_inactive // 60
    mins = minutes_inactive % 60
    time_str = f"{hours}h {mins}m" if hours else f"{mins} daqiqa"

    return (
        f"\u2744\ufe0f <b>Lead Cooling Down</b>\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\U0001f321 Temperature: {lead_temperature.upper()}\n"
        f"\u23f0 Last interaction: {time_str} ago\n\n"
        f"<b>Recommendation:</b>\n{recommended_action_uz}"
    )


def build_insight_alert(
    *,
    lead_id: int,
    lead_name: str,
    health_score: int,
    signals: list[str],
    risk_level: str,
    recommended_action_uz: str,
) -> str:
    """Build a conversation insight alert for admin group (HTML)."""
    _SIGNAL_LABELS = {
        "interest": "\U0001f7e2 Qiziqish",
        "hesitation": "\U0001f7e1 Ikkilanish",
        "confusion": "\U0001f535 Tushunmaslik",
        "price_resistance": "\U0001f534 Narx qarshiligi",
        "silence_risk": "\u26a0\ufe0f Sukunat xavfi",
        "strong_intent": "\U0001f7e2 Kuchli niyat",
        "cooling": "\u2744\ufe0f Sovumoqda",
        "engaged": "\U0001f7e2 Faol",
        "objection_unresolved": "\U0001f534 E'tiroz ochiq",
    }
    _RISK_BADGES = {
        "low": "\U0001f7e2", "medium": "\U0001f7e1",
        "high": "\U0001f534", "critical": "\u26d4",
    }

    signal_text = ", ".join(
        _SIGNAL_LABELS.get(s, s) for s in signals[:4]
    ) or "\u2014"
    risk_badge = _RISK_BADGES.get(risk_level, "\u26aa")

    return (
        f"\U0001f4ca <b>Conversation Insight</b>\n\n"
        f"\U0001f4cb Lead: #{lead_id} — {lead_name}\n"
        f"\U0001f3af Health Score: {health_score}/100\n"
        f"{risk_badge} Risk: {risk_level.upper()}\n"
        f"\U0001f4e1 Signals: {signal_text}\n\n"
        f"<b>Recommendation:</b>\n{recommended_action_uz}"
    )


# ── Quality score ──────────────────────────────────────────────────────────


def _compute_quality_score(
    *,
    score: int,
    phone_captured: bool,
    area_m2: float | None,
    has_district: bool,
    follow_up_count: int,
    closing_confidence: float | None,
    last_closing_attempt: str | None,
    last_objection: str | None,
    last_negotiation_tactic: str | None,
    current_stage: str,
) -> int:
    """Compute conversation quality score (0-100).

    Measures how well the conversation is progressing:
    - Data collected (phone, area, district)
    - Engagement level (score)
    - Objection resolution (tactic applied after objection)
    - Pipeline progress (stage advancement)
    """
    quality = 20  # base

    # Data collection quality (max +30)
    if phone_captured:
        quality += 15
    if area_m2 is not None:
        quality += 10
    if has_district:
        quality += 5

    # Engagement quality (max +20)
    if score >= 60:
        quality += 20
    elif score >= 40:
        quality += 12
    elif score >= 20:
        quality += 5

    # Objection resolution quality (max +15)
    if last_objection and last_negotiation_tactic:
        quality += 15  # objection was addressed with a tactic
    elif last_objection:
        quality -= 5  # objection exists but no tactic applied

    # Closing attempt quality (+10)
    if last_closing_attempt:
        quality += 10

    # Pipeline progress (max +15)
    _STAGE_QUALITY = {
        "COMPLETED": 15, "INSTALLATION": 15, "DEAL": 12,
        "QUOTE": 10, "MEASUREMENT": 8, "CONTACTED": 5,
        "PACKAGE_SELECTED": 3,
    }
    quality += _STAGE_QUALITY.get(current_stage, 0)

    # Confidence bonus (+10)
    if closing_confidence is not None and closing_confidence >= 0.5:
        quality += 10

    # Follow-up penalty (too many = ineffective)
    if follow_up_count >= 5:
        quality -= 10
    elif follow_up_count >= 3:
        quality -= 5

    return max(0, min(100, quality))


# ── Action picker ──────────────────────────────────────────────────────────


def _pick_action(
    *,
    health: int,
    signals: list[str],
    score: int,
    phone_captured: bool,
    area_m2: float | None,
    buyer_type: str | None,
    cooling: bool,
    follow_up_count: int,
    last_objection: str | None,
    minutes_since_last_activity: int,
) -> str:
    """Pick the best next action based on conversation state."""

    # Critical: escalate
    if health <= 25 and score >= 40:
        return "escalate_manager"

    # Cooling: reactivation or follow-up
    if cooling:
        if score >= 50 and phone_captured:
            return "schedule_measurement"
        if minutes_since_last_activity >= 1440:  # 24h+
            return "reactivation"
        return "soft_followup"

    # Price resistance → offer discount/cheaper option
    if "price_resistance" in signals:
        if buyer_type == "price_sensitive":
            return "offer_discount"
        return "offer_discount"

    # Confusion → clarify
    if "confusion" in signals:
        return "ask_clarification"

    # Hesitation → depends on what's missing
    if "hesitation" in signals:
        if not phone_captured:
            return "send_catalog"
        if area_m2 is None:
            return "ask_clarification"
        return "schedule_measurement"

    # Strong intent / engaged → push closing
    if "strong_intent" in signals or score >= 60:
        if phone_captured and area_m2 is not None:
            return "schedule_measurement"
        if phone_captured:
            return "urgency_offer"
        return "ask_clarification"

    # Engaged but missing data
    if "engaged" in signals or score >= 30:
        if area_m2 is None:
            return "ask_clarification"
        if not phone_captured:
            return "send_catalog"
        return "schedule_measurement"

    # Follow-up fatigue
    if follow_up_count >= 4:
        return "wait"

    # Low activity, low score → soft approach
    if minutes_since_last_activity >= 60:
        return "soft_followup"

    return "no_action"


# ── Public labels for admin rendering ──────────────────────────────────────

RISK_LABELS: dict[str, str] = {
    "low": "Past",
    "medium": "O'rta",
    "high": "Yuqori",
    "critical": "Kritik",
}

SIGNAL_LABELS: dict[str, str] = {
    "interest": "Qiziqish",
    "hesitation": "Ikkilanish",
    "confusion": "Tushunmaslik",
    "price_resistance": "Narx qarshiligi",
    "silence_risk": "Sukunat xavfi",
    "strong_intent": "Kuchli niyat",
    "cooling": "Sovumoqda",
    "engaged": "Faol",
    "objection_unresolved": "E'tiroz ochiq",
}
