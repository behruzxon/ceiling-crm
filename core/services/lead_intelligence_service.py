"""
core.services.lead_intelligence_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic buyer-type classification for leads.

Identifies one of four psychological buyer types based on CRM signals
that are already collected by the AI chat, lead scoring, deal probability,
and sales closer modules.  This is a **complementary layer** — it does NOT
replace HOT/WARM/COLD scoring or the deal probability engine.

Buyer types
-----------
  price_sensitive  — budget-conscious, asks about price, objects on cost
  quality_buyer    — cares about design / materials / premium options
  fast_buyer       — decisive, shares phone quickly, accepts CTA
  research_buyer   — gathering information, long conversations, no commitment

Usage::

    from core.services.lead_intelligence_service import analyze_buyer_type

    profile = analyze_buyer_type(
        score=65,
        phone_captured=True,
        has_area=True,
        has_district=True,
        closing_attempted=True,
        last_objection=None,
        intent="price",
        design_type="mramor",
        follow_up_count=0,
        closing_confidence=0.7,
    )
    # profile.buyer_type == "fast_buyer"
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BuyerProfile:
    """Structured buyer-type assessment for a lead."""

    buyer_type: str
    """One of: price_sensitive | quality_buyer | fast_buyer | research_buyer."""

    confidence: float
    """0.0-1.0 confidence in the classification."""

    strategy: str
    """Short Uzbek-language strategy recommendation for the admin."""

    reasons: list[str] = field(default_factory=list)
    """Human-readable reasons (Uzbek) explaining the classification."""


# ── Type labels & strategies ─────────────────────────────────────────────────

_TYPE_LABELS: dict[str, str] = {
    "price_sensitive": "Narxga sezgir",
    "quality_buyer":   "Sifat xaridori",
    "fast_buyer":      "Tez qaror",
    "research_buyer":  "Tadqiqotchi",
}

_TYPE_STRATEGIES: dict[str, str] = {
    "price_sensitive": "Chegirma yoki byudjet variantini taklif qiling",
    "quality_buyer":   "Premium dizaynlarni ko'rsating va o'lchov taklif qiling",
    "fast_buyer":      "Darhol qo'ng'iroq qiling va buyurtmani rasmiylashtiing",
    "research_buyer":  "Batafsil ma'lumot yuboring va 24 soatdan keyin follow-up",
}

# ── Premium design keywords ─────────────────────────────────────────────────

_PREMIUM_DESIGNS: frozenset[str] = frozenset({
    "hi-tech", "hitech", "mramor", "naqsh", "kosmos", "osmon",
    "qora uf", "qora", "gulli",
})


# ── Scoring engine ───────────────────────────────────────────────────────────


def analyze_buyer_type(
    *,
    score: int = 0,
    phone_captured: bool = False,
    has_area: bool = False,
    has_district: bool = False,
    closing_attempted: bool = False,
    closing_action: str | None = None,
    last_objection: str | None = None,
    intent: str | None = None,
    design_type: str | None = None,
    follow_up_count: int = 0,
    closing_confidence: float | None = None,
    deal_probability_percent: int | None = None,
) -> BuyerProfile:
    """Classify the psychological buyer type from available CRM signals.

    All parameters are keyword-only with safe defaults so callers can
    pass only what they have.  The function is pure (no I/O) and
    deterministic.
    """
    # Compute raw scores for each buyer type
    scores: dict[str, float] = {
        "price_sensitive": _score_price_sensitive(
            last_objection=last_objection,
            intent=intent,
            design_type=design_type,
            closing_attempted=closing_attempted,
        ),
        "quality_buyer": _score_quality_buyer(
            design_type=design_type,
            intent=intent,
            has_area=has_area,
            closing_confidence=closing_confidence,
            last_objection=last_objection,
        ),
        "fast_buyer": _score_fast_buyer(
            phone_captured=phone_captured,
            closing_attempted=closing_attempted,
            score=score,
            has_area=has_area,
            has_district=has_district,
            follow_up_count=follow_up_count,
        ),
        "research_buyer": _score_research_buyer(
            follow_up_count=follow_up_count,
            phone_captured=phone_captured,
            closing_attempted=closing_attempted,
            intent=intent,
            score=score,
        ),
    }

    # Pick winner
    winner = max(scores, key=scores.get)  # type: ignore[arg-type]
    winner_score = scores[winner]

    # Confidence = normalised gap between winner and runner-up
    sorted_scores = sorted(scores.values(), reverse=True)
    runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
    total = winner_score + runner_up if (winner_score + runner_up) > 0 else 1.0
    confidence = round(
        max(0.3, min(1.0, winner_score / total)),
        2,
    )

    # Build reasons
    reasons = _build_reasons(
        winner,
        last_objection=last_objection,
        intent=intent,
        design_type=design_type,
        phone_captured=phone_captured,
        closing_attempted=closing_attempted,
        has_area=has_area,
        has_district=has_district,
        follow_up_count=follow_up_count,
        score=score,
        closing_confidence=closing_confidence,
    )

    return BuyerProfile(
        buyer_type=winner,
        confidence=confidence,
        strategy=_TYPE_STRATEGIES[winner],
        reasons=reasons,
    )


# ── Per-type scoring functions ───────────────────────────────────────────────


def _score_price_sensitive(
    *,
    last_objection: str | None,
    intent: str | None,
    design_type: str | None,
    closing_attempted: bool,
) -> float:
    pts = 0.0
    if last_objection == "expensive":
        pts += 4.0
    if intent == "price":
        pts += 2.5
    if not design_type:
        pts += 1.0
    if last_objection == "compare":
        pts += 1.5
    if closing_attempted:
        pts -= 1.0  # engaged with CTA → less price-only
    return max(0.0, pts)


def _score_quality_buyer(
    *,
    design_type: str | None,
    intent: str | None,
    has_area: bool,
    closing_confidence: float | None,
    last_objection: str | None,
) -> float:
    pts = 0.0
    if design_type:
        pts += 3.0
        if design_type.lower().strip() in _PREMIUM_DESIGNS:
            pts += 1.5
    if intent == "catalog":
        pts += 2.0
    if has_area:
        pts += 1.0
    if closing_confidence is not None and closing_confidence >= 0.6:
        pts += 1.0
    if last_objection == "expensive":
        pts -= 2.0  # price concern contradicts quality focus
    return max(0.0, pts)


def _score_fast_buyer(
    *,
    phone_captured: bool,
    closing_attempted: bool,
    score: int,
    has_area: bool,
    has_district: bool,
    follow_up_count: int,
) -> float:
    pts = 0.0
    if phone_captured:
        pts += 3.5
    if closing_attempted:
        pts += 2.5
    if score >= 50:
        pts += 2.0
    elif score >= 30:
        pts += 1.0
    if has_area and has_district:
        pts += 1.0
    if follow_up_count >= 2:
        pts -= 2.0  # needed reminders → not fast
    return max(0.0, pts)


def _score_research_buyer(
    *,
    follow_up_count: int,
    phone_captured: bool,
    closing_attempted: bool,
    intent: str | None,
    score: int,
) -> float:
    pts = 0.0
    if follow_up_count >= 2:
        pts += 3.0
    elif follow_up_count == 1:
        pts += 1.5
    if not phone_captured:
        pts += 2.0
    if not closing_attempted:
        pts += 1.5
    if intent in ("catalog", "faq"):
        pts += 1.0
    if phone_captured:
        pts -= 2.5  # committed → not just researching
    if score >= 50:
        pts -= 1.0  # high engagement → likely not passive researcher
    return max(0.0, pts)


# ── Reason builder ───────────────────────────────────────────────────────────


def _build_reasons(
    buyer_type: str,
    *,
    last_objection: str | None,
    intent: str | None,
    design_type: str | None,
    phone_captured: bool,
    closing_attempted: bool,
    has_area: bool,
    has_district: bool,
    follow_up_count: int,
    score: int,
    closing_confidence: float | None,
) -> list[str]:
    """Build a short list of human-readable reasons for the classification."""
    reasons: list[str] = []

    if buyer_type == "price_sensitive":
        if last_objection == "expensive":
            reasons.append("Narx bo'yicha e'tiroz bildirilgan")
        if intent == "price":
            reasons.append("Narx so'ragan")
        if last_objection == "compare":
            reasons.append("Boshqalar bilan taqqoslagan")
        if not design_type:
            reasons.append("Dizayn tanlamagan")

    elif buyer_type == "quality_buyer":
        if design_type:
            reasons.append(f"Dizayn tanlangan: {design_type}")
        if intent == "catalog":
            reasons.append("Katalog ko'rgan")
        if has_area:
            reasons.append("Xona o'lchami ma'lum")
        if closing_confidence is not None and closing_confidence >= 0.6:
            reasons.append("Yuqori qiziqish")

    elif buyer_type == "fast_buyer":
        if phone_captured:
            reasons.append("Telefon raqam ulashgan")
        if closing_attempted:
            reasons.append("Closing CTA qabul qilgan")
        if score >= 50:
            reasons.append("Yuqori lid bali")
        if has_area and has_district:
            reasons.append("O'lcham va manzil ma'lum")

    elif buyer_type == "research_buyer":
        if follow_up_count >= 2:
            reasons.append("Ko'p follow-up kerak bo'lgan")
        if not phone_captured:
            reasons.append("Telefon raqam ulashmagan")
        if not closing_attempted:
            reasons.append("CTA qabul qilmagan")
        if intent in ("catalog", "faq"):
            reasons.append("Ma'lumot izlagan")

    return reasons[:4]  # cap at 4 reasons
