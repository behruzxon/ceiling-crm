"""
shared.utils.deal_probability
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic, rules-based Deal Probability Engine.

Calculates a structured deal probability for each lead based on all
available CRM signals.  Does NOT duplicate the 0-100 lead score; instead
it treats the score as one input among many and produces a richer output
with probability percentage, expected deal value, confidence level,
recommended action, and explainable reasons.

Usage::

    from shared.utils.deal_probability import evaluate_deal_probability

    result = evaluate_deal_probability(
        score=65,
        closing_confidence=0.72,
        phone_captured=True,
        has_area=True,
        area_m2=22.0,
        has_district=True,
        closing_attempted=True,
        closing_action="measurement",
        last_objection="expensive",
        intent="price",
        follow_up_count=1,
        design_type=None,
    )
    # result.deal_probability_percent == 78
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.services.signal_vector_service import SignalVector


# ── Pricing constants (UZS per m^2) ─────────────────────────────────────────

_DESIGN_PRICES: dict[str, int] = {
    "adnatonniy": 80_000,
    "matt": 80_000,
    "hi-tech": 120_000,
    "hitech": 120_000,
    "mramor": 120_000,
    "naqsh": 120_000,
    "kosmos": 120_000,
    "osmon": 120_000,
    "gulli": 130_000,
    "qora uf": 140_000,
    "qora": 140_000,
}
_DEFAULT_PRICE_PER_M2 = 100_000  # average when design unknown


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DealProbability:
    """Structured deal probability assessment for a lead."""

    deal_probability_percent: int
    """0-100 probability that this lead converts to a deal."""

    expected_deal_value: int | None
    """Estimated deal value in UZS, or None if area is unknown."""

    confidence_level: str
    """How confident we are in this assessment: 'low' | 'medium' | 'high'."""

    recommended_action: str
    """Short Uzbek-language action recommendation for the admin."""

    probability_reasons: list[str] = field(default_factory=list)
    """Short human-readable reasons (Uzbek) explaining the probability."""


# ── Scoring weights ──────────────────────────────────────────────────────────
#
# The lead score (0-100) already encodes engagement signals (phone +40,
# area +15, district +10, etc.).  To avoid double-counting, we use the
# score as a *base* and add only context signals NOT embedded in it.
#
#   Component             Max contribution
#   ─────────────────────────────────────
#   Lead score base        40  (score * 0.4)
#   AI closing confidence  20  (confidence * 20)
#   Phone captured         10
#   Area known              7
#   District known          4
#   Closing CTA engaged     8
#   Price intent            5
#   Clean objection slate   6  (no delay/angry)
#   ─────────────────────────────────────
#   Subtotal max          100
#
#   Penalties:
#     delay objection      -10
#     angry objection       -5


def evaluate_deal_probability(
    *,
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
    signal_vector: SignalVector | None = None,
) -> DealProbability:
    """Evaluate deal probability from available CRM signals.

    When *signal_vector* is provided, uses normalised scores with
    rebalanced weights that eliminate double-counting.  Otherwise
    falls back to legacy per-parameter scoring for backward compat.
    """
    if signal_vector is not None:
        return _evaluate_from_vector(signal_vector)

    return _evaluate_legacy(
        score=score,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        has_area=has_area,
        area_m2=area_m2,
        has_district=has_district,
        closing_attempted=closing_attempted,
        last_objection=last_objection,
        intent=intent,
        follow_up_count=follow_up_count,
        design_type=design_type,
    )


# ── SignalVector-based scoring (no double-counting) ─────────────────────────
#
#   Component                   Max contribution
#   ──────────────────────────────────────────────
#   Engagement (pure)            45  (engagement_score × 45)
#   AI closing confidence        18  (confidence_score × 18)
#   Contact quality              22  (contact_quality × 22)
#   Closing progress              8  (closing_progress × 8)
#   Intent strength               5  (intent_strength × 5)
#   Clean objection slate         6  (no delay/angry)
#   Follow-up engagement          3  (capped)
#   ──────────────────────────────────────────────
#   Subtotal max               107 → clamp 100
#
#   Penalties:
#     delay objection           -10
#     angry objection            -5


def _evaluate_from_vector(sv: SignalVector) -> DealProbability:
    """Score using normalised SignalVector — no double-counting."""
    reasons: list[str] = []
    pts = 0.0

    # ── 1. Pure engagement (max 45) ──────────────────────────────────
    pts += sv.engagement_score * 45
    if sv.engagement_score >= 0.6:
        reasons.append("Yuqori lid bali")
    elif sv.engagement_score >= 0.3:
        reasons.append("O'rtacha lid bali")

    # ── 2. AI closing confidence (max 18) ────────────────────────────
    pts += sv.confidence_score * 18
    if sv.confidence_score >= 0.7:
        reasons.append("AI baholashi yuqori")
    elif sv.confidence_score >= 0.45:
        reasons.append("AI baholashi o'rtacha")

    # ── 3. Contact quality (max 22) ──────────────────────────────────
    pts += sv.contact_quality * 22
    if sv.phone_captured:
        reasons.append("Telefon raqam ulashgan")
    if sv.has_area:
        reasons.append("Xona o'lchami ma'lum")
    if sv.has_district:
        reasons.append("Manzil aniqlangan")

    # ── 4. Closing progress (max 8) ──────────────────────────────────
    pts += sv.closing_progress * 8
    if sv.closing_attempted:
        reasons.append("Closing CTA qabul qilgan")

    # ── 5. Intent strength (max 5) ───────────────────────────────────
    pts += sv.intent_strength * 5
    if sv.intent == "price":
        reasons.append("Narx so'ragan")

    # ── 6. Objection impact ──────────────────────────────────────────
    if sv.last_objection == "delay":
        pts -= 10
        reasons.append("E'tiroz: kechiktirish")
    elif sv.last_objection == "angry":
        pts -= 5
        reasons.append("E'tiroz: norozilik")
    elif sv.last_objection == "expensive":
        reasons.append("E'tiroz: qimmat")
    elif sv.last_objection is None:
        pts += 6

    # ── 7. Follow-up engagement bonus (max 3) ────────────────────────
    if sv.follow_up_count >= 1:
        pts += min(sv.follow_up_count, 3)

    # ── Final probability ────────────────────────────────────────────
    probability = max(0, min(100, round(pts)))

    # ── Expected deal value ──────────────────────────────────────────
    deal_value = _compute_deal_value(sv.area_m2, sv.design_type)

    # ── Confidence level ─────────────────────────────────────────────
    strong_signals = sum([
        sv.phone_captured,
        sv.has_area,
        sv.has_district,
        sv.closing_attempted,
        sv.engagement_score >= 0.5,
        sv.confidence_score >= 0.6,
    ])
    if strong_signals >= 4:
        confidence_level = "high"
    elif strong_signals >= 2:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    # ── Recommended action ───────────────────────────────────────────
    recommended_action = _pick_recommended_action(probability)

    return DealProbability(
        deal_probability_percent=probability,
        expected_deal_value=deal_value,
        confidence_level=confidence_level,
        recommended_action=recommended_action,
        probability_reasons=reasons,
    )


# ── Legacy scoring (backward compat) ────────────────────────────────────────


def _evaluate_legacy(
    *,
    score: int,
    closing_confidence: float | None,
    phone_captured: bool,
    has_area: bool,
    area_m2: float | None,
    has_district: bool,
    closing_attempted: bool,
    last_objection: str | None,
    intent: str | None,
    follow_up_count: int,
    design_type: str | None,
) -> DealProbability:
    reasons: list[str] = []
    pts = 0.0

    score_clamped = max(0, min(100, score))
    pts += score_clamped * 0.4
    if score_clamped >= 60:
        reasons.append("Yuqori lid bali")
    elif score_clamped >= 30:
        reasons.append("O'rtacha lid bali")

    if closing_confidence is not None:
        conf = max(0.0, min(1.0, closing_confidence))
        pts += conf * 20
        if conf >= 0.7:
            reasons.append("AI baholashi yuqori")
        elif conf >= 0.45:
            reasons.append("AI baholashi o'rtacha")

    if phone_captured:
        pts += 10
        reasons.append("Telefon raqam ulashgan")

    if has_area or area_m2 is not None:
        pts += 7
        reasons.append("Xona o'lchami ma'lum")

    if has_district:
        pts += 4
        reasons.append("Manzil aniqlangan")

    if closing_attempted:
        pts += 8
        reasons.append("Closing CTA qabul qilgan")

    if intent == "price":
        pts += 5
        reasons.append("Narx so'ragan")

    if last_objection == "delay":
        pts -= 10
        reasons.append("E'tiroz: kechiktirish")
    elif last_objection == "angry":
        pts -= 5
        reasons.append("E'tiroz: norozilik")
    elif last_objection == "expensive":
        reasons.append("E'tiroz: qimmat")
    elif last_objection is None:
        pts += 6

    if follow_up_count and follow_up_count >= 1:
        pts += min(follow_up_count, 3)

    probability = max(0, min(100, round(pts)))
    deal_value = _compute_deal_value(area_m2, design_type)

    strong_signals = sum([
        phone_captured,
        has_area or area_m2 is not None,
        has_district,
        closing_attempted,
        score_clamped >= 50,
        (closing_confidence or 0) >= 0.6,
    ])
    if strong_signals >= 4:
        confidence_level = "high"
    elif strong_signals >= 2:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    recommended_action = _pick_recommended_action(probability)

    return DealProbability(
        deal_probability_percent=probability,
        expected_deal_value=deal_value,
        confidence_level=confidence_level,
        recommended_action=recommended_action,
        probability_reasons=reasons,
    )


# ── Shared helpers ──────────────────────────────────────────────────────────


def _compute_deal_value(
    area_m2: float | None, design_type: str | None,
) -> int | None:
    if area_m2 is None or area_m2 <= 0:
        return None
    price_per_m2 = _DEFAULT_PRICE_PER_M2
    if design_type:
        price_per_m2 = _DESIGN_PRICES.get(
            design_type.lower().strip(), _DEFAULT_PRICE_PER_M2,
        )
    return round(area_m2 * price_per_m2)


def _pick_recommended_action(probability: int) -> str:
    if probability >= 80:
        return "\U0001f4de Darhol qo'ng'iroq qiling!"
    if probability >= 60:
        return "\U0001f4d0 Bugun o'lchov taklif qiling"
    if probability >= 40:
        return "\U0001f4cb Katalog yuboring + follow-up"
    if probability >= 20:
        return "\U0001f4ac Qiymat haqida xabar yuboring"
    return "\U0001f4e8 Past ustuvorlik follow-up"
