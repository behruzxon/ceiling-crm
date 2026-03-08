"""
core.services.lead_scoring_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unified, rule-based lead scoring engine.

Pure function — no I/O, no imports from ``apps/`` or ``infrastructure/``.
Takes all available CRM signals and produces a multidimensional score with
signal classifications, human-readable reasons, and an operator attention flag.

Called from ``_update_lead_ai_scoring()`` after every AI interaction.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Result ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """Multidimensional scoring output for a single lead."""

    score: int                           # 0-100 composite
    lead_temperature: str                # cold / warm / hot
    urgency_signal: str                  # high / medium / low
    budget_signal: str                   # high / medium / low
    engagement_signal: str               # high / medium / low
    objection_signal: str                # none / mild / strong
    scoring_reasons: list[str] = field(default_factory=list)  # max 5 Uzbek strings
    operator_attention: bool = False


# ── Public API ────────────────────────────────────────────────────────────────


def score_lead(
    *,
    raw_score: int = 0,
    closing_confidence: float | None = None,
    phone_captured: bool = False,
    has_area: bool = False,
    area_m2: float | None = None,
    has_district: bool = False,
    design_type: str | None = None,
    intent: str | None = None,
    last_objection: str | None = None,
    closing_attempted: bool = False,
    follow_up_count: int = 0,
    package_type: str | None = None,
    negotiation_escalated: bool = False,
    assigned_manager_id: int | None = None,
) -> ScoringResult:
    """Compute a comprehensive lead score from all available signals.

    All parameters are keyword-only with safe defaults.
    Callers can pass only what they have.
    """
    urgency = _classify_urgency(
        intent=intent,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        raw_score=raw_score,
        closing_attempted=closing_attempted,
        has_area=has_area,
    )
    budget = _classify_budget(
        has_area=has_area,
        design_type=design_type,
        last_objection=last_objection,
        package_type=package_type,
        intent=intent,
    )
    engagement = _classify_engagement(
        raw_score=raw_score,
        follow_up_count=follow_up_count,
        closing_attempted=closing_attempted,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
    )
    objection = _classify_objection(
        last_objection=last_objection,
        negotiation_escalated=negotiation_escalated,
    )

    adjusted = _compute_adjusted_score(raw_score, urgency, budget, engagement, objection)
    temperature = _classify_temperature(adjusted)

    reasons = _build_scoring_reasons(
        phone_captured=phone_captured,
        has_area=has_area,
        area_m2=area_m2,
        intent=intent,
        closing_attempted=closing_attempted,
        design_type=design_type,
        last_objection=last_objection,
        negotiation_escalated=negotiation_escalated,
        adjusted_score=adjusted,
        follow_up_count=follow_up_count,
    )

    attention = _determine_operator_attention(
        urgency=urgency,
        objection=objection,
        engagement=engagement,
        temperature=temperature,
        phone_captured=phone_captured,
        negotiation_escalated=negotiation_escalated,
        adjusted_score=adjusted,
        assigned_manager_id=assigned_manager_id,
    )

    return ScoringResult(
        score=adjusted,
        lead_temperature=temperature,
        urgency_signal=urgency,
        budget_signal=budget,
        engagement_signal=engagement,
        objection_signal=objection,
        scoring_reasons=reasons,
        operator_attention=attention,
    )


# ── Signal classifiers ───────────────────────────────────────────────────────


def _classify_urgency(
    *,
    intent: str | None,
    closing_confidence: float | None,
    phone_captured: bool,
    raw_score: int,
    closing_attempted: bool,
    has_area: bool,
) -> str:
    # HIGH: strong buying intent with contact info
    if intent in ("order", "measurement") and phone_captured:
        return "high"
    if raw_score >= 70 and closing_attempted and has_area:
        return "high"
    if intent == "order" and has_area:
        return "high"

    # MEDIUM: moderate interest signals
    if intent == "price" and raw_score >= 30:
        return "medium"
    if phone_captured and raw_score >= 40:
        return "medium"
    if has_area and (closing_confidence or 0) >= 0.4:
        return "medium"

    return "low"


def _classify_budget(
    *,
    has_area: bool,
    design_type: str | None,
    last_objection: str | None,
    package_type: str | None,
    intent: str | None,
) -> str:
    # HIGH: clear budget signals, no price objection
    if has_area and design_type and last_objection != "expensive":
        return "high"
    if package_type in ("premium", "vip"):
        return "high"

    # MEDIUM: some pricing interest
    if intent == "price":
        return "medium"
    if has_area and last_objection == "expensive":
        return "medium"
    if package_type == "standard":
        return "medium"

    return "low"


def _classify_engagement(
    *,
    raw_score: int,
    follow_up_count: int,
    closing_attempted: bool,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
) -> str:
    # HIGH: deep engagement
    if raw_score >= 50 and (follow_up_count >= 1 or closing_attempted):
        return "high"
    if phone_captured and has_area and has_district:
        return "high"

    # MEDIUM: moderate engagement
    if 20 <= raw_score < 50:
        return "medium"
    if has_area or has_district:
        return "medium"

    return "low"


def _classify_objection(
    *,
    last_objection: str | None,
    negotiation_escalated: bool,
) -> str:
    if last_objection == "angry":
        return "strong"
    if last_objection == "delay" and negotiation_escalated:
        return "strong"

    if last_objection in ("expensive", "trust", "compare"):
        return "mild"

    return "none"


# ── Score computation ─────────────────────────────────────────────────────────

_SIGNAL_BONUSES: dict[str, dict[str, int]] = {
    "urgency": {"high": 10, "medium": 5, "low": 0},
    "budget": {"high": 8, "medium": 3, "low": 0},
    "engagement": {"high": 7, "medium": 3, "low": 0},
    "objection": {"none": 5, "mild": 0, "strong": -8},
}


def _compute_adjusted_score(
    raw_score: int,
    urgency: str,
    budget: str,
    engagement: str,
    objection: str,
) -> int:
    bonus = (
        _SIGNAL_BONUSES["urgency"].get(urgency, 0)
        + _SIGNAL_BONUSES["budget"].get(budget, 0)
        + _SIGNAL_BONUSES["engagement"].get(engagement, 0)
        + _SIGNAL_BONUSES["objection"].get(objection, 0)
    )
    return max(0, min(100, raw_score + bonus))


def _classify_temperature(score: int) -> str:
    if score >= 70:
        return "hot"
    if score >= 35:
        return "warm"
    return "cold"


# ── Operator attention ────────────────────────────────────────────────────────


def _determine_operator_attention(
    *,
    urgency: str,
    objection: str,
    engagement: str,
    temperature: str,
    phone_captured: bool,
    negotiation_escalated: bool,
    adjusted_score: int,
    assigned_manager_id: int | None,
) -> bool:
    # Unassigned hot urgent lead
    if urgency == "high" and adjusted_score >= 70 and assigned_manager_id is None:
        return True
    # Strong objection — needs human
    if objection == "strong":
        return True
    # High engagement + hot but no phone — operator can push
    if engagement == "high" and temperature == "hot" and not phone_captured:
        return True
    # Negotiation escalated to manager
    if negotiation_escalated:
        return True
    return False


# ── Reason builder ────────────────────────────────────────────────────────────


def _build_scoring_reasons(
    *,
    phone_captured: bool,
    has_area: bool,
    area_m2: float | None,
    intent: str | None,
    closing_attempted: bool,
    design_type: str | None,
    last_objection: str | None,
    negotiation_escalated: bool,
    adjusted_score: int,
    follow_up_count: int,
) -> list[str]:
    reasons: list[str] = []

    if phone_captured:
        reasons.append("Telefon raqam berdi")
    if has_area and area_m2 is not None:
        reasons.append(f"Xona o'lchami: {area_m2:.0f}m\u00b2")
    if intent == "order":
        reasons.append("Buyurtma niyati yuqori")
    elif intent == "measurement":
        reasons.append("O'lchov so'radi")
    elif intent == "price":
        reasons.append("Narx so'radi")
    if closing_attempted:
        reasons.append("Closing CTA qabul qildi")
    if design_type:
        reasons.append(f"Dizayn tanlagan: {design_type}")
    if last_objection == "expensive":
        reasons.append("Narx e'tirozi")
    elif last_objection == "delay":
        reasons.append("Kechiktirish niyati")
    elif last_objection == "angry":
        reasons.append("Norozilik bildirdi")
    if negotiation_escalated:
        reasons.append("Menejer kerak")
    if adjusted_score >= 70:
        reasons.append("Yuqori xarid niyati")
    if follow_up_count >= 2:
        reasons.append(f"{follow_up_count}x follow-up javob berdi")

    return reasons[:5]
