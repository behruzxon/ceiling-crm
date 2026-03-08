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
) -> DealProbability:
    """Evaluate deal probability from available CRM signals.

    All parameters are keyword-only and optional with safe defaults,
    so callers can pass only what they have.
    """
    reasons: list[str] = []
    pts = 0.0

    # ── 1. Lead score base (max 40) ──────────────────────────────────────
    score_clamped = max(0, min(100, score))
    pts += score_clamped * 0.4
    if score_clamped >= 60:
        reasons.append("Yuqori lid bali")
    elif score_clamped >= 30:
        reasons.append("O'rtacha lid bali")

    # ── 2. AI closing confidence (max 20) ────────────────────────────────
    if closing_confidence is not None:
        conf = max(0.0, min(1.0, closing_confidence))
        pts += conf * 20
        if conf >= 0.7:
            reasons.append("AI baholashi yuqori")
        elif conf >= 0.45:
            reasons.append("AI baholashi o'rtacha")

    # ── 3. Phone captured (+10) ──────────────────────────────────────────
    if phone_captured:
        pts += 10
        reasons.append("Telefon raqam ulashgan")

    # ── 4. Area known (+7) ───────────────────────────────────────────────
    if has_area or area_m2 is not None:
        pts += 7
        reasons.append("Xona o'lchami ma'lum")

    # ── 5. District known (+4) ───────────────────────────────────────────
    if has_district:
        pts += 4
        reasons.append("Manzil aniqlangan")

    # ── 6. Closing CTA engaged (+8) ─────────────────────────────────────
    if closing_attempted:
        pts += 8
        reasons.append("Closing CTA qabul qilgan")

    # ── 7. Price intent (+5) ─────────────────────────────────────────────
    if intent == "price":
        pts += 5
        reasons.append("Narx so'ragan")

    # ── 8. Clean objection slate (+6) / penalties ────────────────────────
    if last_objection == "delay":
        pts -= 10
        reasons.append("E'tiroz: kechiktirish")
    elif last_objection == "angry":
        pts -= 5
        reasons.append("E'tiroz: norozilik")
    elif last_objection == "expensive":
        # Not penalised — engagement signal, already in score
        reasons.append("E'tiroz: qimmat")
    elif last_objection is None:
        pts += 6

    # ── 9. Follow-up engagement bonus ────────────────────────────────────
    if follow_up_count and follow_up_count >= 1:
        # Each follow-up response is mild engagement; cap bonus at 3
        pts += min(follow_up_count, 3)

    # ── Final probability ────────────────────────────────────────────────
    probability = max(0, min(100, round(pts)))

    # ── Expected deal value (UZS) ────────────────────────────────────────
    deal_value: int | None = None
    if area_m2 is not None and area_m2 > 0:
        price_per_m2 = _DEFAULT_PRICE_PER_M2
        if design_type:
            price_per_m2 = _DESIGN_PRICES.get(
                design_type.lower().strip(), _DEFAULT_PRICE_PER_M2
            )
        deal_value = round(area_m2 * price_per_m2)

    # ── Confidence level ─────────────────────────────────────────────────
    # Based on how many strong signals we have (more signals = higher
    # confidence in our probability estimate, regardless of the
    # probability itself).
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

    # ── Recommended action ───────────────────────────────────────────────
    if probability >= 80:
        recommended_action = "\U0001f4de Darhol qo'ng'iroq qiling!"
    elif probability >= 60:
        recommended_action = "\U0001f4d0 Bugun o'lchov taklif qiling"
    elif probability >= 40:
        recommended_action = "\U0001f4cb Katalog yuboring + follow-up"
    elif probability >= 20:
        recommended_action = "\U0001f4ac Qiymat haqida xabar yuboring"
    else:
        recommended_action = "\U0001f4e8 Past ustuvorlik follow-up"

    return DealProbability(
        deal_probability_percent=probability,
        expected_deal_value=deal_value,
        confidence_level=confidence_level,
        recommended_action=recommended_action,
        probability_reasons=reasons,
    )
