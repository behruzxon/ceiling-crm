"""
core.services.negotiation_engine_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic negotiation tactic selector for all objection types.

When a lead raises an objection the engine selects the best tactic based on
objection type, severity, and available CRM signals, then generates a short,
sales-safe Uzbek reply.

Tactics (price-related)
-----------------------
  value_reframe       — reframe value (quality + warranty)
  cheaper_alternative — offer budget design option
  package_simplify    — suggest simpler package / fewer addons
  urgency_close       — time-limited offer / seasonal push

Tactics (trust/delay/angry)
---------------------------
  trust_proof         — show guarantees, real work photos, warranty
  soft_delay          — no pressure, keep door open, soft CTA
  calm_deescalate     — empathetic de-escalation + practical redirect

Shared
------
  manager_escalation  — hand off to human manager (any HIGH severity)

Usage::

    from core.services.negotiation_engine_service import analyze_negotiation

    result = analyze_negotiation(
        objection_type="expensive",
        severity="medium",
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
    """Structured negotiation analysis for an objection."""

    negotiation_detected: bool
    """True if this objection is a negotiation opportunity."""

    negotiation_type: str
    """'price' | 'comparison' | 'trust' | 'delay' | 'angry' | 'none'."""

    tactic: str
    """Selected tactic name."""

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
    "trust_proof": "Ishonch dalillari",
    "soft_delay": "Yumshoq kechiktirish",
    "calm_deescalate": "Tinchlantiruv",
    "manager_escalation": "Menejerga uzatish",
    "none": "\u2014",
}


# ── Negotiation replies by tactic ────────────────────────────────────────────

_NEGOTIATION_REPLIES: dict[str, str] = {
    # Price tactics
    "value_reframe": (
        "Tushunaman, narx muhim. Lekin bizning materiallar 15 yil kafolat "
        "bilan keladi \u2014 boshqa kompaniyalarda 3-5 yil. Qayta ta\u2019mir xarajati "
        "yo\u2018q, uzoq muddatda tejaysiz. Aniq hisoblab beraman \u2014 "
        "maydon nechchi m\u00b2?"
    ),
    "cheaper_alternative": (
        "Sizga mos arzonroq variant ham bor! Adnatonniy yoki Matt dizayn "
        "sifatli va 80 000 so\u2018m/m\u00b2 dan boshlanadi. "
        "Xona maydonini aytsangiz, aniq narx chiqaraman \U0001f642"
    ),
    "package_simplify": (
        "Asosiy potolok narxi eng yaxshi \u2014 qo\u2018shimchalar (LED, karniz) "
        "ixtiyoriy. Avval faqat asosiy potolokni hisoblaymizmi? "
        "Maydon nechchi m\u00b2?"
    ),
    "urgency_close": (
        "Hozir maxsus narx amal qilmoqda \u2014 bu oy oxirigacha. "
        "Bepul o\u2018lchov buyurtma qilsangiz, aniq narxni joyida aytaman. "
        "Qaysi kun qulay?"
    ),
    # Trust tactics
    "trust_proof": (
        "Tushunaman, ishonch muhim. Bizda 15 yil rasmiy kafolat, "
        "yuzlab tayyor ishlar fotosi bor. Xohlasangiz real ishlarimiz "
        "rasmlarini ko\u2018rsataman. Sizga qaysi xona uchun kerak?"
    ),
    # Delay tactics
    "soft_delay": (
        "Mayli, shoshilmasangiz ham bo\u2018ladi \U0001f642 Hech qanday majburiyat yo\u2018q. "
        "Tayyor bo\u2018lganingizda yozing \u2014 bepul o\u2018lchov istalgan vaqt. "
        "Shunchaki qaysi xona ekanini aytib qo\u2018ying, tayyorlab qo\u2018yaman."
    ),
    # Angry tactics
    "calm_deescalate": (
        "Uzr, bezovta qilgan bo\u2018lsam. Faqat yordam bermoqchi edim \U0001f642 "
        "Agar kerak bo\u2018lsa \u2014 katalog, narx hisobi yoki bepul o\u2018lchov \u2014 "
        "istalgan payt yozing. Yaxshi kun tilayman!"
    ),
    # Shared escalation
    "manager_escalation": (
        "Tushundim, sizga maxsus taklif kerak. Menejerimiz siz bilan "
        "bog\u2018lanib, eng yaxshi variantni taklif qiladi. "
        "Telefon raqamingizni yuboring \U0001f4de"
    ),
}


# ── Premium designs (shared with other modules) ─────────────────────────────

_PREMIUM_DESIGNS: frozenset[str] = frozenset({
    "hi-tech", "hitech", "mramor", "naqsh", "kosmos", "osmon",
    "qora uf", "qora", "gulli",
})


# ── Main analyzer ───────────────────────────────────────────────────────────


_OBJECTION_TYPE_MAP: dict[str, str] = {
    "expensive": "price",
    "compare": "comparison",
    "trust": "trust",
    "delay": "delay",
    "angry": "angry",
}

_VALID_OBJECTION_TYPES: frozenset[str] = frozenset(_OBJECTION_TYPE_MAP)


def analyze_negotiation(
    *,
    objection_type: str | None = None,
    severity: str = "low",
    area_m2: float | None = None,
    design_type: str | None = None,
    score: int = 0,
    buyer_type: str | None = None,
    closing_confidence: float | None = None,
    phone_captured: bool = False,
    closing_attempted: bool = False,
    follow_up_count: int = 0,
    previous_negotiation_tactic: str | None = None,
    tactic_weights: dict[str, float] | None = None,
) -> NegotiationResult:
    """Select the best negotiation tactic for any objection type.

    Supports all 5 objection types: expensive, compare, trust, delay, angry.
    All parameters are keyword-only with safe defaults.
    Returns negotiation_detected=False for unknown objection types.
    """
    if objection_type not in _VALID_OBJECTION_TYPES:
        return NegotiationResult(
            negotiation_detected=False,
            negotiation_type="none",
            tactic="none",
            reply="",
            escalate_to_manager=False,
        )

    neg_type = _OBJECTION_TYPE_MAP[objection_type]
    reasons: list[str] = []

    # ── Select tactic based on signals ───────────────────────────────

    tactic = _select_tactic(
        objection_type=objection_type,
        severity=severity,
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
        tactic_weights=tactic_weights,
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
    severity: str,
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
    tactic_weights: dict[str, float] | None = None,
) -> str:
    """Pick the best tactic for any objection type. Mutates reasons list."""

    # ── Rule 0: HIGH severity on ANY type → escalate immediately ─────
    if severity == "high":
        reasons.append("Yuqori darajali e'tiroz — menejerga uzatish")
        return "manager_escalation"

    # ── Rule 1: Repeated objection + high engagement → escalate ──────
    if follow_up_count >= 2 and score >= 40:
        reasons.append("Ko'p marta e'tiroz + yuqori qiziqish")
        return "manager_escalation"

    # ── Rule 2: Already tried a tactic → rotate to next ──────────────
    if previous_tactic and previous_tactic != "none":
        return _rotate_tactic(previous_tactic, buyer_type, objection_type, reasons, tactic_weights)

    # ── Branch by objection family ───────────────────────────────────

    if objection_type in ("expensive", "compare"):
        return _select_price_tactic(
            objection_type=objection_type,
            area_m2=area_m2,
            design_type=design_type,
            score=score,
            buyer_type=buyer_type,
            closing_confidence=closing_confidence,
            phone_captured=phone_captured,
            closing_attempted=closing_attempted,
            reasons=reasons,
        )

    if objection_type == "trust":
        return _select_trust_tactic(
            score=score,
            phone_captured=phone_captured,
            buyer_type=buyer_type,
            reasons=reasons,
        )

    if objection_type == "delay":
        return _select_delay_tactic(
            score=score,
            area_m2=area_m2,
            phone_captured=phone_captured,
            closing_confidence=closing_confidence,
            reasons=reasons,
        )

    # angry
    reasons.append("G'azablangan xaridor — tinchlantiruv")
    return "calm_deescalate"


def _select_price_tactic(
    *,
    objection_type: str,
    area_m2: float | None,
    design_type: str | None,
    score: int,
    buyer_type: str | None,
    closing_confidence: float | None,
    phone_captured: bool,
    closing_attempted: bool,
    reasons: list[str],
) -> str:
    """Price/compare objection tactic selection (existing rules)."""

    if buyer_type == "price_sensitive":
        reasons.append("Narxga sezgir xaridor")
        return "cheaper_alternative"

    if design_type and design_type.lower().strip() in _PREMIUM_DESIGNS:
        reasons.append(f"Premium dizayn: {design_type}")
        return "value_reframe"

    if objection_type == "compare":
        reasons.append("Raqobatchilar bilan taqqoslash")
        return "value_reframe"

    if score >= 50 and phone_captured:
        reasons.append("Yuqori qiziqish + telefon bor")
        return "urgency_close"

    if area_m2 is not None and not closing_attempted:
        reasons.append("Maydon ma'lum, lekin closing yo'q")
        return "package_simplify"

    if closing_confidence is not None and closing_confidence >= 0.6:
        reasons.append("Yuqori ishonch ko'rsatkichi")
        return "urgency_close"

    reasons.append("Standart narx e'tirozi")
    return "cheaper_alternative"


def _select_trust_tactic(
    *,
    score: int,
    phone_captured: bool,
    buyer_type: str | None,
    reasons: list[str],
) -> str:
    """Trust objection tactic selection."""

    # High engagement + phone → move to urgency (trust is resolved, push close)
    if score >= 50 and phone_captured:
        reasons.append("Ishonch e'tirozi, lekin yuqori qiziqish + telefon")
        return "urgency_close"

    # Quality buyer → reframe value (they appreciate quality assurance)
    if buyer_type == "quality_buyer":
        reasons.append("Sifat xaridori — qiymat qayta baholash")
        return "value_reframe"

    reasons.append("Ishonch e'tirozi — dalillar ko'rsatish")
    return "trust_proof"


def _select_delay_tactic(
    *,
    score: int,
    area_m2: float | None,
    phone_captured: bool,
    closing_confidence: float | None,
    reasons: list[str],
) -> str:
    """Delay objection tactic selection."""

    # High engagement + phone → gentle urgency (don't lose warm lead)
    if score >= 50 and phone_captured:
        reasons.append("Kechiktirish, lekin yuqori qiziqish + telefon")
        return "urgency_close"

    # High confidence → offer simplified package to reduce friction
    if closing_confidence is not None and closing_confidence >= 0.6:
        reasons.append("Yuqori ishonch — paket soddalashtirish")
        return "package_simplify"

    # Has area → show simplified option to keep engaged
    if area_m2 is not None:
        reasons.append("Maydon ma'lum — paket soddalashtirish")
        return "package_simplify"

    reasons.append("Kechiktirish e'tirozi — yumshoq kutish")
    return "soft_delay"


_ROTATION_CHAINS: dict[str, list[str]] = {
    "price": [
        "value_reframe", "cheaper_alternative", "package_simplify",
        "urgency_close", "manager_escalation",
    ],
    "trust": ["trust_proof", "value_reframe", "manager_escalation"],
    "delay": ["soft_delay", "urgency_close", "package_simplify", "manager_escalation"],
    "angry": ["calm_deescalate", "soft_delay", "manager_escalation"],
}

_TYPE_TO_CHAIN: dict[str, str] = {
    "expensive": "price", "compare": "price",
    "trust": "trust", "delay": "delay", "angry": "angry",
}


def _rotate_tactic(
    previous: str,
    buyer_type: str | None,
    objection_type: str,
    reasons: list[str],
    tactic_weights: dict[str, float] | None = None,
) -> str:
    """When a tactic was already used, pick the next one in the chain.

    If adaptive *tactic_weights* are provided (from outcome-based learning),
    pick the highest-weighted candidate instead of sequential rotation.
    """
    chain_key = _TYPE_TO_CHAIN.get(objection_type, "price")
    rotation = _ROTATION_CHAINS.get(chain_key, _ROTATION_CHAINS["price"])

    candidates = [t for t in rotation if t != previous]

    # Use adaptive weights when available — pick best-performing candidate
    if tactic_weights and candidates:
        best = max(candidates, key=lambda t: tactic_weights.get(t, 1.0))
        reasons.append(
            f"Oldingi taktika: {TACTIC_LABELS.get(previous, previous)} "
            f"(adaptive: {TACTIC_LABELS.get(best, best)})"
        )
        return best

    # Fallback: sequential rotation
    try:
        idx = rotation.index(previous)
        next_tactic = rotation[(idx + 1) % len(rotation)]
    except ValueError:
        next_tactic = rotation[0]

    reasons.append(f"Oldingi taktika: {TACTIC_LABELS.get(previous, previous)}")
    return next_tactic
