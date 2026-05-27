"""
core.services.auto_sales_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AI Auto-Seller — smart decision layer for automated sales conversations.

Decides whether the AI can safely auto-reply with a template (no OpenAI),
whether to escalate to the manager, and generates appropriate responses.

Pure deterministic functions — no I/O, fully testable.

Safety rules:
  - Max 2 consecutive auto-replies per user
  - Never auto-reply to angry objections
  - Never auto-reply when health_score < 60
  - Always allow manager override
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Constants ──────────────────────────────────────────────────────────────

MAX_CONSECUTIVE_AUTO_REPLIES = 2
MIN_SCORE_FOR_AUTO_REPLY = 50
MIN_HEALTH_FOR_AUTO_REPLY = 60


# ── Result dataclasses ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AutoReplyDecision:
    """Whether the AI can auto-reply without OpenAI."""

    auto_reply_allowed: bool
    confidence: float
    """0.0–1.0 confidence in auto-reply safety."""

    reason: str
    """Machine-readable reason."""

    reason_uz: str
    """Uzbek reason for admin visibility."""


@dataclass(frozen=True, slots=True)
class AutoReplyResult:
    """Generated auto-reply content."""

    reply_text: str
    """Uzbek reply text ready to send."""

    reply_type: str
    """Category: price|measurement|material|package|greeting|general."""

    next_step_suggestion: str
    """Suggested next step for the conversation."""


@dataclass(frozen=True, slots=True)
class EscalationResult:
    """Whether the conversation should be escalated to manager."""

    should_escalate: bool
    urgency: str
    """'low' | 'medium' | 'high'."""

    reason: str
    """Machine-readable reason."""

    reason_uz: str
    """Uzbek reason for admin alert."""

    suggested_action_uz: str
    """What the manager should do."""

    escalation_signals: list[str] = field(default_factory=list)


# ── Reply templates ────────────────────────────────────────────────────────

REPLY_TEMPLATES: dict[str, dict] = {
    "price_inquiry": {
        "text": ("Aniq narxni o'lchov asosida ayta olamiz. " "Bepul o'lchov buyurtma qilasizmi?"),
        "next_step": "o'lchov taklif qilish",
    },
    "measurement_interest": {
        "text": ("Ustamiz bepul o'lchov qilib berishi mumkin. " "Qaysi vaqt sizga qulay bo'ladi?"),
        "next_step": "vaqt kelishish",
    },
    "material_question": {
        "text": (
            "Bizda bir nechta variant bor \u2014 mat, glossy va satin. "
            "Qaysi rang yoki dizayn qiziqtiryapti?"
        ),
        "next_step": "katalog ko'rsatish",
    },
    "package_question": {
        "text": ("Tayyor paketlarimiz bor \u2014 oddiydan premiumgacha. " "Ko'rib chiqasizmi?"),
        "next_step": "paket tafsilotlari",
    },
    "greeting": {
        "text": ("Assalomu alaykum! Stretch potalok bo'yicha yordam beramiz. " "Qanday savol bor?"),
        "next_step": "ehtiyoj aniqlash",
    },
    "general_followup": {
        "text": (
            "Qanday savol bo'lsa yozing, yordam beramiz! "
            "Narx yoki katalog haqida ma'lumot kerakmi?"
        ),
        "next_step": "qiziqish aniqlash",
    },
}

# Buyer-type personalized variants
_BUYER_TYPE_VARIANTS: dict[str, dict[str, str]] = {
    "price_sensitive": {
        "price_inquiry": (
            "Eng arzon variantimiz bor. Aniq narxni o'lchov asosida "
            "aytamiz \u2014 bepul o'lchov buyurtma qilasizmi?"
        ),
        "package_question": (
            "Eng qulay narxdagi paketimiz bor. " "Tafsilotlarini ko'rsatib beraymi?"
        ),
    },
    "quality_buyer": {
        "price_inquiry": (
            "Premium material va professional o'rnatish bilan ishlaimiz. "
            "Bepul o'lchov qilib, aniq narx beramiz."
        ),
        "material_question": (
            "Eng sifatli materiallarimiz \u2014 Germaniya va Belgiya ishlab chiqarishi. "
            "Qaysi xonangiz uchun kerak?"
        ),
    },
    "fast_buyer": {
        "price_inquiry": ("Tezkor hisob beramiz. Bepul o'lchov \u2014 bugunoq bo'ladimi?"),
        "measurement_interest": ("Bugunoq o'lchov qila olamiz. Qaysi soat qulay?"),
    },
}

REPLY_TYPE_LABELS: dict[str, str] = {
    "price_inquiry": "Narx so'rovi",
    "measurement_interest": "O'lchov qiziqishi",
    "material_question": "Material savoli",
    "package_question": "Paket savoli",
    "greeting": "Salomlashish",
    "general_followup": "Umumiy savol",
}


# ── Auto-Reply Decision Engine ────────────────────────────────────────────


def decide_auto_reply(
    *,
    score: int = 0,
    health_score: int = 50,
    last_objection: str | None = None,
    objection_severity: str | None = None,
    consecutive_auto_replies: int = 0,
    negotiation_escalated: bool = False,
    lead_temperature: str | None = None,
    closing_confidence: float | None = None,
    follow_up_count: int = 0,
) -> AutoReplyDecision:
    """Decide whether the AI can safely auto-reply with a template.

    Returns AutoReplyDecision with confidence score.
    """
    temp = (lead_temperature or "").lower()
    sev = (objection_severity or "").lower()

    # ── BLOCK conditions (hard stops) ──────────────────────────────
    if consecutive_auto_replies >= MAX_CONSECUTIVE_AUTO_REPLIES:
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="consecutive_limit_reached",
            reason_uz="Ketma-ket avto-javob limiti yetdi",
        )

    if last_objection == "angry":
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="angry_objection",
            reason_uz="Norozilik e'tirozi \u2014 menejer kerak",
        )

    if sev == "high":
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="high_severity_objection",
            reason_uz="Yuqori darajali e'tiroz \u2014 menejer kerak",
        )

    if negotiation_escalated:
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="negotiation_escalated",
            reason_uz="Muzokara menejerga o'tkazilgan",
        )

    if health_score < MIN_HEALTH_FOR_AUTO_REPLY:
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="low_health_score",
            reason_uz="Suhbat salomatligi past",
        )

    if temp == "cold" and score < 30:
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="cold_low_score",
            reason_uz="Sovuq lid \u2014 shaxsiy yondashuv kerak",
        )

    # ── ALLOW conditions ───────────────────────────────────────────
    if score < MIN_SCORE_FOR_AUTO_REPLY:
        return AutoReplyDecision(
            auto_reply_allowed=False,
            confidence=0.0,
            reason="score_too_low",
            reason_uz="Ball yetarli emas avto-javob uchun",
        )

    # ── Compute confidence ─────────────────────────────────────────
    conf = 0.0

    # Score contribution (0-0.30)
    if score >= 70:
        conf += 0.30
    elif score >= 50:
        conf += 0.20

    # Health contribution (0-0.25)
    if health_score >= 80:
        conf += 0.25
    elif health_score >= 60:
        conf += 0.15

    # No objection bonus (0-0.15)
    if not last_objection:
        conf += 0.15
    elif sev == "low":
        conf += 0.10

    # Temperature bonus (0-0.15)
    if temp == "hot":
        conf += 0.15
    elif temp == "warm":
        conf += 0.10

    # Closing confidence bonus (0-0.10)
    c_conf = closing_confidence or 0.0
    if c_conf >= 0.6:
        conf += 0.10
    elif c_conf >= 0.3:
        conf += 0.05

    # First auto-reply is safer (0-0.05)
    if consecutive_auto_replies == 0:
        conf += 0.05

    conf = min(1.0, conf)

    reason = "healthy conversation with sufficient score"
    reason_uz = "Sog'lom suhbat, yetarli ball \u2014 avto-javob xavfsiz"

    if last_objection and sev in ("low", "medium"):
        reason = f"mild {last_objection} objection, manageable"
        reason_uz = "Yengil e'tiroz \u2014 avto-javob mumkin"

    return AutoReplyDecision(
        auto_reply_allowed=True,
        confidence=round(conf, 2),
        reason=reason,
        reason_uz=reason_uz,
    )


# ── Auto-Reply Generator ──────────────────────────────────────────────────


def generate_auto_reply(
    *,
    intent: str | None = None,
    buyer_type: str | None = None,
    has_area: bool = False,
    has_phone: bool = False,
    has_district: bool = False,
    last_objection: str | None = None,
) -> AutoReplyResult:
    """Generate a template-based auto-reply.

    Picks the best template based on detected intent and buyer type.
    Returns Uzbek reply text + type tag.
    """
    # Map intent to template key
    reply_key = _map_intent_to_template(
        intent=intent,
        has_area=has_area,
        has_phone=has_phone,
        last_objection=last_objection,
    )

    # Check for buyer-type variant
    text = None
    if buyer_type and buyer_type in _BUYER_TYPE_VARIANTS:
        variants = _BUYER_TYPE_VARIANTS[buyer_type]
        text = variants.get(reply_key)

    # Fallback to default template
    if not text:
        template = REPLY_TEMPLATES.get(reply_key, REPLY_TEMPLATES["general_followup"])
        text = template["text"]

    next_step = REPLY_TEMPLATES.get(reply_key, REPLY_TEMPLATES["general_followup"])["next_step"]

    return AutoReplyResult(
        reply_text=text,
        reply_type=reply_key,
        next_step_suggestion=next_step,
    )


def _map_intent_to_template(
    *,
    intent: str | None,
    has_area: bool,
    has_phone: bool,
    last_objection: str | None,
) -> str:
    """Map conversation intent to template key."""
    if intent in ("price", "narx"):
        return "price_inquiry"
    if intent in ("measurement", "o'lchov"):
        return "measurement_interest"
    if intent in ("material", "dizayn", "rang"):
        return "material_question"
    if intent in ("catalog", "katalog", "package", "paket"):
        return "package_question"
    if intent in ("greeting", "salom"):
        return "greeting"

    # Contextual fallback based on collected data
    if has_area and not has_phone:
        return "measurement_interest"
    if last_objection in ("expensive", "compare"):
        return "package_question"

    return "general_followup"


# ── Auto-Escalation Logic ─────────────────────────────────────────────────


def should_escalate(
    *,
    last_objection: str | None = None,
    objection_severity: str | None = None,
    consecutive_auto_replies: int = 0,
    health_score: int = 50,
    negotiation_escalated: bool = False,
    follow_up_count: int = 0,
    score: int = 0,
    closing_confidence: float | None = None,
) -> EscalationResult:
    """Determine whether the conversation requires manager intervention.

    Returns EscalationResult with urgency level and suggested action.
    """
    signals: list[str] = []
    sev = (objection_severity or "").lower()

    # ── HIGH urgency ───────────────────────────────────────────────
    if last_objection == "angry":
        signals.append("angry_objection")
        return EscalationResult(
            should_escalate=True,
            urgency="high",
            reason="angry_customer",
            reason_uz="Mijoz norozilik bildirmoqda",
            suggested_action_uz="Mijozni tinglang va muammoni hal qiling. Kechirim so'rang.",
            escalation_signals=signals,
        )

    if sev == "high" and score >= 40:
        signals.append("high_severity_valuable_lead")
        return EscalationResult(
            should_escalate=True,
            urgency="high",
            reason="high_severity_valuable_lead",
            reason_uz="Qimmatli lid yuqori darajali e'tirozga ega",
            suggested_action_uz=("Shaxsan qo'ng'iroq qiling. " "Sifat va kafolatni tushuntiring."),
            escalation_signals=signals,
        )

    # ── MEDIUM urgency ─────────────────────────────────────────────
    if negotiation_escalated:
        signals.append("negotiation_escalated")
        return EscalationResult(
            should_escalate=True,
            urgency="medium",
            reason="negotiation_requires_manager",
            reason_uz="Muzokara menejer aralashuvini talab qiladi",
            suggested_action_uz="Maxsus narx yoki chegirma taklif qiling.",
            escalation_signals=signals,
        )

    if consecutive_auto_replies >= MAX_CONSECUTIVE_AUTO_REPLIES and health_score < 50:
        signals.append("auto_reply_exhausted_low_health")
        return EscalationResult(
            should_escalate=True,
            urgency="medium",
            reason="auto_reply_limit_low_health",
            reason_uz="Avto-javob limiti va past suhbat sifati",
            suggested_action_uz=("Shaxsiy xabar yuboring yoki qo'ng'iroq qiling."),
            escalation_signals=signals,
        )

    if sev == "high":
        signals.append("high_severity_objection")
        return EscalationResult(
            should_escalate=True,
            urgency="medium",
            reason="high_severity_objection",
            reason_uz="Yuqori darajali e'tiroz bor",
            suggested_action_uz="E'tirozni shaxsan hal qiling.",
            escalation_signals=signals,
        )

    # ── LOW urgency ────────────────────────────────────────────────
    if follow_up_count >= 4 and score < 40:
        signals.append("followup_fatigue_low_progress")
        return EscalationResult(
            should_escalate=True,
            urgency="low",
            reason="stalled_conversation",
            reason_uz="Suhbat to'xtab qolgan \u2014 ko'p follow-up, kam natija",
            suggested_action_uz="Reactivation yuboring yoki boshqa yondashuvdan foydalaning.",
            escalation_signals=signals,
        )

    # ── No escalation needed ───────────────────────────────────────
    return EscalationResult(
        should_escalate=False,
        urgency="low",
        reason="no_escalation_needed",
        reason_uz="Menejer kerak emas",
        suggested_action_uz="",
        escalation_signals=[],
    )


# ── Alert Builders ────────────────────────────────────────────────────────


def build_escalation_alert(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    reason_uz: str,
    last_message: str,
    suggested_action_uz: str,
    urgency: str,
) -> str:
    """Build HTML alert for manager escalation."""
    _badges = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}
    badge = _badges.get(urgency, "\u26aa")

    truncated_msg = last_message[:120] + "..." if len(last_message) > 120 else last_message

    return (
        f"\u26a0\ufe0f <b>Manager Needed</b> {badge}\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\u26a0\ufe0f Sabab: {reason_uz}\n"
        f"\U0001f4ac Oxirgi xabar: <i>{truncated_msg}</i>\n\n"
        f"<b>Tavsiya:</b> {suggested_action_uz}"
    )


def build_auto_reply_log_text(
    *,
    lead_id: int,
    reply_type: str,
    confidence: float,
) -> str:
    """Build compact log line for auto-reply tracking."""
    label = REPLY_TYPE_LABELS.get(reply_type, reply_type)
    return f"Auto-reply: #{lead_id} | {label} | {confidence:.0%}"


def build_stalled_conversation_alert(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    minutes_waiting: int,
    last_auto_reply_type: str,
) -> str:
    """Build alert for conversations stalled after auto-reply."""
    label = REPLY_TYPE_LABELS.get(last_auto_reply_type, last_auto_reply_type)
    return (
        "\U0001f551 <b>Stalled Conversation</b>\n\n"
        f"\U0001f4cb Lead: #{lead_id}\n"
        f"\U0001f464 {lead_name} | {lead_phone}\n"
        f"\u23f0 Kutish: {minutes_waiting} daqiqa\n"
        f"\U0001f4ac Oxirgi avto-javob: {label}\n\n"
        "<b>Tavsiya:</b> Shaxsiy xabar yuboring"
    )


# ── Analytics Helper ──────────────────────────────────────────────────────


def compute_auto_sales_metrics(leads_data: list[dict]) -> dict:
    """Compute auto-sales metrics from enriched lead dicts.

    Expects optional keys: ``auto_reply_used``, ``auto_escalated``,
    ``auto_reply_confidence``.
    """
    auto_reply_count = 0
    escalation_count = 0
    confidences: list[float] = []

    for ld in leads_data:
        if ld.get("auto_reply_used"):
            auto_reply_count += 1
            conf = ld.get("auto_reply_confidence")
            if conf is not None:
                confidences.append(conf)
        if ld.get("auto_escalated"):
            escalation_count += 1

    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    return {
        "auto_reply_count": auto_reply_count,
        "auto_escalation_count": escalation_count,
        "auto_reply_confidence_avg": avg_conf,
    }
