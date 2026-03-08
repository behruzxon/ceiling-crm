"""
core.services.negotiation_engine_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic negotiation tactic selector for price objections.

When a lead raises a price-related objection (expensive, compare) the engine
selects the best negotiation tactic based on available CRM signals and
generates a short, sales-safe Uzbek reply that replaces the generic canned
objection response.

Tactics
-------
  value_reframe       — reframe value (quality + warranty)
  cheaper_alternative — offer budget design option
  package_simplify    — suggest simpler package / fewer addons
  urgency_close       — time-limited offer / seasonal push
  manager_escalation  — hand off to human manager

Usage::

    from core.services.negotiation_engine_service import analyze_negotiation

    result = analyze_negotiation(
        objection_type="expensive",
        area_m2=22.0,
        design_type="mramor",
        score=45,
        buyer_type="price_sensitive",
    )
    # result.tactic == "cheaper_alternative"
    # result.reply == "..."
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NegotiationResult:
    """Structured negotiation analysis for a price objection."""

    negotiation_detected: bool
    """True if this objection is a negotiation opportunity."""

    negotiation_type: str
    """'price' | 'comparison' | 'none' — type of negotiation detected."""

    tactic: str
    """Selected tactic: value_reframe | cheaper_alternative |
    package_simplify | urgency_close | manager_escalation | none."""

    reply: str
    """Uzbek-language negotiation reply. Empty when not detected."""

    escalate_to_manager: bool
    """True when the engine recommends human manager intervention."""

    reasons: list[str] = field(default_factory=list)
    """Human-readable reasons (Uzbek) explaining tactic selection."""


# ── Tactic labels for admin visibility ───────────────────────────────────────

TACTIC_LABELS: dict[str, str] = {
    "value_reframe": "Qiymat qayta baholash",
    "cheaper_alternative": "Arzon variant taklifi",
    "package_simplify": "Paket soddalashtirish",
    "urgency_close": "Shoshilinch taklif",
    "manager_escalation": "Menejerga uzatish",
    "none": "—",
}


# ── Negotiation replies by tactic ────────────────────────────────────────────

_NEGOTIATION_REPLIES: dict[str, str] = {
    "value_reframe": (
        "Tushunaman, narx muhim. Lekin bizning materiallar 15 yil kafolat "
        "bilan keladi — boshqa kompaniyalarda 3-5 yil. Qayta ta'mir xarajati "
        "yo'q, uzoq muddatda tejaysiz. Aniq hisoblab beraman — "
        "maydon nechchi m²?"
    ),
    "cheaper_alternative": (
        "Sizga mos arzonroq variant ham bor! Adnatonniy yoki Matt dizayn "
        "sifatli va 80 000 so'm/m² dan boshlanadi. "
        "Xona maydonini aytsangiz, aniq narx chiqaraman 🙂"
    ),
    "package_simplify": (
        "Asosiy potolok narxi eng yaxshi — qo'shimchalar (LED, karniz) "
        "ixtiyoriy. Avval faqat asosiy potolokni hisoblaymizmi? "
        "Maydon nechchi m²?"
    ),
    "urgency_close": (
        "Hozir maxsus narx amal qilmoqda — bu oy oxirigacha. "
        "Bepul o'lchov buyurtma qilsangiz, aniq narxni joyida aytaman. "
        "Qaysi kun qulay?"
    ),
    "manager_escalation": (
        "Tushundim, sizga maxsus taklif kerak. Menejerimiz siz bilan "
        "bog'lanib, eng yaxshi variantni taklif qiladi. "
        "Telefon raqamingizni yuboring 📞"
    ),
}


# ── Premium designs (shared with other modules) ─────────────────────────────

_PREMIUM_DESIGNS: frozenset[str] = frozenset({
    "hi-tech", "hitech", "mramor", "naqsh", "kosmos", "osmon",
    "qora uf", "qora", "gulli",
})


# ── Main analyzer ───────────────────────────────────────────────────────────


def analyze_negotiation(
    *,
    objection_type: str | None = None,
    area_m2: float | None = None,
    design_type: str | None = None,
    score: int = 0,
    buyer_type: str | None = None,
    closing_confidence: float | None = None,
    phone_captured: bool = False,
    closing_attempted: bool = False,
    follow_up_count: int = 0,
    previous_negotiation_tactic: str | None = None,
) -> NegotiationResult:
    """Select the best negotiation tactic for a price objection.

    All parameters are keyword-only with safe defaults.
    Returns negotiation_detected=False for non-price objections.
    """
    # Only negotiate on price-related objections
    if objection_type not in ("expensive", "compare"):
        return NegotiationResult(
            negotiation_detected=False,
            negotiation_type="none",
            tactic="none",
            reply="",
            escalate_to_manager=False,
        )

    neg_type = "price" if objection_type == "expensive" else "comparison"
    reasons: list[str] = []

    # ── Select tactic based on signals ───────────────────────────────

    tactic = _select_tactic(
        objection_type=objection_type,
        area_m2=area_m2,
        design_type=design_type,
        score=score,
        buyer_type=buyer_type,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        closing_attempted=closing_attempted,
        follow_up_count=follow_up_count,
        previous_tactic=previous_negotiation_tactic,
        reasons=reasons,
    )

    escalate = tactic == "manager_escalation"
    reply = _NEGOTIATION_REPLIES.get(tactic, "")

    return NegotiationResult(
        negotiation_detected=True,
        negotiation_type=neg_type,
        tactic=tactic,
        reply=reply,
        escalate_to_manager=escalate,
        reasons=reasons[:4],
    )


def _select_tactic(
    *,
    objection_type: str,
    area_m2: float | None,
    design_type: str | None,
    score: int,
    buyer_type: str | None,
    closing_confidence: float | None,
    phone_captured: bool,
    closing_attempted: bool,
    follow_up_count: int,
    previous_tactic: str | None,
    reasons: list[str],
) -> str:
    """Pick the best tactic. Mutates reasons list."""

    # ── Rule 1: Repeated objection + high engagement → escalate ──────
    if follow_up_count >= 2 and score >= 40:
        reasons.append("Ko'p marta e'tiroz + yuqori qiziqish")
        return "manager_escalation"

    # ── Rule 2: Already tried a tactic → rotate to next ──────────────
    if previous_tactic and previous_tactic != "none":
        return _rotate_tactic(previous_tactic, buyer_type, reasons)

    # ── Rule 3: Price-sensitive buyer → cheaper alternative ──────────
    if buyer_type == "price_sensitive":
        reasons.append("Narxga sezgir xaridor")
        return "cheaper_alternative"

    # ── Rule 4: Premium design + expensive objection → value reframe ─
    if design_type and design_type.lower().strip() in _PREMIUM_DESIGNS:
        reasons.append(f"Premium dizayn: {design_type}")
        return "value_reframe"

    # ── Rule 5: Comparison objection → value reframe ─────────────────
    if objection_type == "compare":
        reasons.append("Raqobatchilar bilan taqqoslash")
        return "value_reframe"

    # ── Rule 6: High score + phone → urgency close ───────────────────
    if score >= 50 and phone_captured:
        reasons.append("Yuqori qiziqish + telefon bor")
        return "urgency_close"

    # ── Rule 7: Has area but no closing → package simplify ───────────
    if area_m2 is not None and not closing_attempted:
        reasons.append("Maydon ma'lum, lekin closing yo'q")
        return "package_simplify"

    # ── Rule 8: High confidence → urgency close ──────────────────────
    if closing_confidence is not None and closing_confidence >= 0.6:
        reasons.append("Yuqori ishonch ko'rsatkichi")
        return "urgency_close"

    # ── Default: cheaper alternative (safest) ────────────────────────
    reasons.append("Standart narx e'tirozi")
    return "cheaper_alternative"


def _rotate_tactic(
    previous: str, buyer_type: str | None, reasons: list[str]
) -> str:
    """When a tactic was already used, pick a different one."""

    # Rotation order: value_reframe → cheaper_alternative → package_simplify
    # → urgency_close → manager_escalation
    rotation = [
        "value_reframe",
        "cheaper_alternative",
        "package_simplify",
        "urgency_close",
        "manager_escalation",
    ]

    try:
        idx = rotation.index(previous)
        next_tactic = rotation[(idx + 1) % len(rotation)]
    except ValueError:
        next_tactic = "cheaper_alternative"

    reasons.append(f"Oldingi taktika: {TACTIC_LABELS.get(previous, previous)}")
    return next_tactic
