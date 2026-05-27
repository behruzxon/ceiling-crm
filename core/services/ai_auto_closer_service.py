"""
core.services.ai_auto_closer_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Real-time operator reply suggestions for closing leads.

Sits on top of :func:`build_sales_brain` — selects a closing strategy
and generates a single recommended Uzbek reply text.

Pure function — no I/O, no DB, no Redis. Fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.services.ai_sales_brain_service import SalesBrainDecision, build_sales_brain

# ── Strategies ───────────────────────────────────────────────────────────────

STRATEGY_LABELS: dict[str, str] = {
    "budget_option": "Byudjet variant",
    "premium_design": "Premium dizayn",
    "measurement_push": "O'lchov taklifi",
    "direct_close": "To'g'ridan-to'g'ri sotish",
    "soft_followup": "Yumshoq follow-up",
}

_STRATEGY_REPLIES: dict[str, tuple[str, str]] = {
    # (template_with_name, template_without_name)
    "budget_option": (
        "{name}, byudjetga mos variantlar ham bor.\n" "Xohlasangiz yuborib beray?",
        "Byudjetga mos variantlar ham bor.\n" "Xohlasangiz yuborib beray?",
    ),
    "premium_design": (
        "{name}, premium dizaynlarimiz juda chiroyli chiqadi.\n" "Katalogdan ko'rsatib beraymi?",
        "Premium dizaynlarimiz juda chiroyli chiqadi.\n" "Katalogdan ko'rsatib beraymi?",
    ),
    "measurement_push": (
        "{name}, bepul o'lchov xizmati bor.\n"
        "Usta yuborib, aniq narx aytib berishimiz mumkin.\n"
        "Qachon qulay bo'ladi?",
        "Bepul o'lchov xizmati bor.\n"
        "Usta yuborib, aniq narx aytib berishimiz mumkin.\n"
        "Qachon qulay bo'ladi?",
    ),
    "direct_close": (
        "{name}, hamma narsa tayyor.\n" "Bugun yoki ertaga usta yuboramizmi?",
        "Hamma narsa tayyor.\n" "Bugun yoki ertaga usta yuboramizmi?",
    ),
    "soft_followup": (
        "{name}, qiziqsangiz yordamlashaman.\n" "Savollaringiz bo'lsa yozing 😊",
        "Qiziqsangiz yordamlashaman.\n" "Savollaringiz bo'lsa yozing 😊",
    ),
}

# Stage contribution to confidence (0.0-1.0)
_STAGE_CONFIDENCE: dict[str, float] = {
    "close_ready": 1.0,
    "negotiating": 0.75,
    "comparing": 0.5,
    "researching": 0.35,
    "new_interest": 0.25,
    "delayed": 0.2,
    "cold": 0.1,
}


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AutoCloseDecision:
    """Operator-facing auto-close suggestion."""

    close_probability: float
    buyer_type: str | None
    objection_type: str | None
    recommended_strategy: str
    recommended_reply: str
    confidence: float
    reason_summary: list[str] = field(default_factory=list)


# ── Private helpers ──────────────────────────────────────────────────────────


def _select_strategy(
    *,
    brain: SalesBrainDecision,
    last_objection: str | None,
    intent: str | None,
    phone_captured: bool,
) -> str:
    """Pick the best closing strategy from brain output."""
    # Rule 1: Price-sensitive buyer or price objection → budget
    if brain.buyer_type == "price_sensitive":
        return "budget_option"
    if last_objection in ("expensive", "compare"):
        return "budget_option"

    # Rule 2: Quality buyer or catalog intent → premium design
    if brain.buyer_type == "quality_buyer":
        return "premium_design"
    if intent == "catalog":
        return "premium_design"

    # Rule 3: Close-ready or high-probability with phone → direct close
    if brain.stage == "close_ready":
        return "direct_close"
    if phone_captured and brain.win_probability >= 50:
        return "direct_close"

    # Rule 4: Researching/comparing/delayed without phone → measurement push
    if brain.stage in ("researching", "comparing", "delayed") and not phone_captured:
        return "measurement_push"

    # Rule 5: Fast buyer with any signal → direct close
    if brain.buyer_type == "fast_buyer" and brain.win_probability >= 30:
        return "direct_close"

    # Default: soft follow-up
    return "soft_followup"


def _build_reply(strategy: str, name: str | None) -> str:
    """Pick the Uzbek reply template for the strategy."""
    templates = _STRATEGY_REPLIES.get(strategy, _STRATEGY_REPLIES["soft_followup"])
    if name:
        return templates[0].format(name=name)
    return templates[1]


def _compute_confidence(brain: SalesBrainDecision) -> float:
    """Weighted composite confidence from brain signals."""
    buyer_conf = brain.buyer_confidence  # 0.0-1.0
    win_conf = brain.win_probability / 100.0  # 0.0-1.0
    stage_conf = _STAGE_CONFIDENCE.get(brain.stage, 0.25)

    raw = buyer_conf * 0.3 + win_conf * 0.4 + stage_conf * 0.3
    return round(min(max(raw, 0.0), 1.0), 2)


def _build_reasons(
    brain: SalesBrainDecision,
    strategy: str,
    last_objection: str | None,
) -> list[str]:
    """Build 2-4 short reason strings from brain output."""
    reasons: list[str] = []

    # Strategy justification
    reasons.append(f"Strategiya: {STRATEGY_LABELS.get(strategy, strategy)}")

    # Buyer type
    if brain.buyer_type:
        _bt_labels = {
            "price_sensitive": "Narxga sezgir",
            "quality_buyer": "Sifat xaridori",
            "fast_buyer": "Tez qaror",
            "research_buyer": "Tadqiqotchi",
        }
        reasons.append(f"Xaridor: {_bt_labels.get(brain.buyer_type, brain.buyer_type)}")

    # Objection
    if last_objection:
        _obj_labels = {
            "expensive": "Qimmat deydi",
            "compare": "Solishtirmoqda",
            "delay": "Kechiktirmoqda",
            "trust": "Ishonch muammo",
            "angry": "Norozilik",
        }
        reasons.append(f"E'tiroz: {_obj_labels.get(last_objection, last_objection)}")

    # Win probability
    reasons.append(f"Sotish ehtimoli: {brain.win_probability}%")

    return reasons[:4]


# ── Main function ────────────────────────────────────────────────────────────


def build_auto_close_reply(
    *,
    # Lead identity
    name: str | None = None,
    district: str | None = None,
    phone: str | None = None,
    # Core signals (passed through to build_sales_brain)
    score: int = 0,
    closing_confidence: float | None = None,
    phone_captured: bool = False,
    has_area: bool = False,
    area_m2: float | None = None,
    has_district: bool = False,
    closing_attempted: bool = False,
    closing_action: str | None = None,
    last_objection: str | None = None,
    intent: str | None = None,
    follow_up_count: int = 0,
    design_type: str | None = None,
    # Negotiation state
    negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    previous_negotiation_tactic: str | None = None,
    # Timing
    last_activity_ts: int | None = None,
    memory_created_at: int | None = None,
    # Follow-up state
    lead_temperature: str | None = None,
    previous_fu_type: str | None = None,
    # Lead status
    lead_status: str | None = None,
    package_type: str | None = None,
) -> AutoCloseDecision:
    """Build a real-time auto-close suggestion for operators.

    Delegates to :func:`build_sales_brain` for all intelligence,
    then selects a closing strategy and generates a recommended reply.

    Pure function — no I/O, fully deterministic.
    """
    brain = build_sales_brain(
        name=name,
        district=district,
        phone=phone,
        score=score,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        has_area=has_area,
        area_m2=area_m2,
        has_district=has_district,
        closing_attempted=closing_attempted,
        closing_action=closing_action,
        last_objection=last_objection,
        intent=intent,
        follow_up_count=follow_up_count,
        design_type=design_type,
        negotiation_tactic=negotiation_tactic,
        negotiation_escalated=negotiation_escalated,
        previous_negotiation_tactic=previous_negotiation_tactic,
        last_activity_ts=last_activity_ts,
        memory_created_at=memory_created_at,
        lead_temperature=lead_temperature,
        previous_fu_type=previous_fu_type,
        lead_status=lead_status,
        package_type=package_type,
    )

    strategy = _select_strategy(
        brain=brain,
        last_objection=last_objection,
        intent=intent,
        phone_captured=phone_captured,
    )

    reply = _build_reply(strategy, name)
    confidence = _compute_confidence(brain)
    reasons = _build_reasons(brain, strategy, last_objection)

    return AutoCloseDecision(
        close_probability=round(brain.win_probability / 100.0, 2),
        buyer_type=brain.buyer_type,
        objection_type=last_objection,
        recommended_strategy=strategy,
        recommended_reply=reply,
        confidence=confidence,
        reason_summary=reasons,
    )
