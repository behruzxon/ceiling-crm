"""
core.services.sales_dialogue_manager_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sales Dialogue Manager — a **pure, deterministic** conversation planner that
turns the bot from an intent *router* into an independent sales *agent*.

It answers three questions for every customer turn:

  1. **What do we already know?**  -> :class:`CustomerConversationFacts`
     (merged from the current message + FSM state + prior facts).
  2. **What is still missing to move toward an order?** -> :class:`MissingInfo`
     + an :func:`order readiness score <compute_order_readiness>` (0-100).
  3. **What is the single best next move?** -> :class:`SalesDialogueDecision`
     (one action, one warm question, never robotic, never overpromising).

Design principles
-----------------
* **Pure**: no Redis, no DB, no OpenAI, no aiogram, no network. Safe to call
  from any layer and trivially unit-testable.
* **Reuses existing detectors** (``parse_combo``, ``detect_objection_full``,
  ``_is_*``, ``resolve_catalog_link``, ``PriceCalculatorService``,
  ``detect_prompt_injection``, ``is_stop_signal``) — it does NOT re-implement
  price/catalog/operator/order logic.
* **One primary question per turn.** Never asks three things at once.
* **Safe by construction.** Never emits a final price, a fake ETA, a "100%"
  claim, a "bugun/darhol/hozir" time promise, or any secret. Stop and safety
  always win.

Nothing here is wired into the live bot. Integration is gated behind the
``SALES_DIALOGUE_MANAGER_ENABLED`` flag (default ``False``); see
``docs/AI_AGENT_SYSTEM/145_SALES_DIALOGUE_MANAGER_DESIGN.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

# Pure detectors — all no-I/O.
from apps.bot.handlers.private.ai_detection import (
    _build_warranty_quality_reply,
    _is_catalog_request,
    _is_measurement_request,
    _is_operator_request,
    _is_price_query,
    _is_warranty_quality_question,
    parse_combo,
)
from apps.bot.handlers.private.ai_scoring import _build_objection_reply, detect_objection_full
from core.services.catalog_link_resolver_service import resolve_catalog_link
from core.services.followup_scheduler_service import FollowupSchedulerService
from core.services.price_calculator_service import PriceCalculatorService
from shared.utils.sanitize import detect_prompt_injection
from shared.utils.text_normalization import latinize_uz_cyrillic

# ── Next-action vocabulary ──────────────────────────────────────────────────

ANSWER_PRICE = "answer_price"
ASK_AREA = "ask_area"
ASK_DESIGN = "ask_design"
ASK_ROOM = "ask_room"
ASK_DISTRICT = "ask_district"
ASK_PHONE = "ask_phone"
SEND_CATALOG = "send_catalog"
ANSWER_WARRANTY = "answer_warranty"
HANDLE_OBJECTION = "handle_objection"
OFFER_MEASUREMENT = "offer_measurement"
CREATE_HANDOFF = "create_handoff"
POLITE_STOP = "polite_stop"
CLARIFY = "clarify"
SAFETY_BLOCK = "safety_block"

NEXT_ACTIONS: frozenset[str] = frozenset(
    {
        ANSWER_PRICE,
        ASK_AREA,
        ASK_DESIGN,
        ASK_ROOM,
        ASK_DISTRICT,
        ASK_PHONE,
        SEND_CATALOG,
        ANSWER_WARRANTY,
        HANDLE_OBJECTION,
        OFFER_MEASUREMENT,
        CREATE_HANDOFF,
        POLITE_STOP,
        CLARIFY,
        SAFETY_BLOCK,
    }
)

# Intent labels (mirror the system-prompt vocabulary).
INTENT_PRICE = "price"
INTENT_CATALOG = "catalog"
INTENT_MEASUREMENT = "measurement"
INTENT_OPERATOR = "operator"
INTENT_OBJECTION = "objection"
INTENT_WARRANTY = "warranty_quality"
INTENT_STOP = "stop"
INTENT_SAFETY = "safety_block"
INTENT_CLARIFY = "clarification"
INTENT_GREETING = "greeting"
INTENT_GENERIC = "generic_help"

# Conversation stages.
STAGE_GREETING = "greeting"
STAGE_DISCOVERY = "discovery"
STAGE_PRICING = "pricing"
STAGE_CATALOG = "catalog"
STAGE_OBJECTION = "objection"
STAGE_CLOSING = "closing"
STAGE_HANDOFF = "handoff"
STAGE_STOPPED = "stopped"

# Readiness weights (sum to 100 when all present → full data == 100).
_READINESS_WEIGHTS: dict[str, int] = {
    "design_key": 20,
    "area_m2": 25,
    "room_type": 10,
    "district": 15,
    "phone_present": 30,
}

# Map the canonical design display names (from parse_combo) to the
# PriceCalculatorService key style used for estimates.
_DESIGN_DISPLAY_TO_KEY: dict[str, str] = {
    "Gulli": "gulli",
    "Hi Tech": "hi-tech",
    "Mramor": "mramor",
    "Naqsh": "naqsh",
    "Osmon": "osmon",
    "Kosmos": "kosmos",
    "Qora UF": "qora uf",
    "Adnatonniy": "adnatonniy",
    "Pechat": "gulli",
}

# Price-only design aliases that parse_combo does NOT detect (it has no
# "oddiy"). Checked on the raw text so "oddiy nechpul" resolves a design.
_EXTRA_DESIGN_ALIASES: dict[str, str] = {
    "oddiy": "adnatonniy",
    "matoviy": "adnatonniy",
    "satin": "adnatonniy",
    "led": "hi-tech",
    "shadow": "hi-tech",
}

_DESIGN_KEY_TITLES: dict[str, str] = {
    "gulli": "Gulli",
    "hi-tech": "Hi-tech",
    "mramor": "Mramor",
    "naqsh": "Naqsh",
    "osmon": "Osmon",
    "kosmos": "Kosmos",
    "qora uf": "Qora UF",
    "adnatonniy": "Oddiy (Adnatonniy)",
}

# Room detection (canonical -> synonyms). Kept local so "oshxona" never leaks
# into the design slot (PriceCalculator aliases "oshxona"->"osmon").
_ROOM_MAP: dict[str, tuple[str, ...]] = {
    "mehmonxona": ("mehmonxona", "mehmon xona", "zal", "katta xona"),
    "oshxona": ("oshxona", "osh xona", "kuxnya", "kuhnya", "kitchen"),
    "yotoqxona": ("yotoqxona", "yotoq xona", "spalnya", "spalniy"),
    "hammom": ("hammom", "vanna", "dush", "sanuzel"),
    "bolalar xonasi": ("bolalar", "detskiy", "bolalar xonasi"),
    "koridor": ("koridor",),
    "terassa": ("terassa", "teras", "veranda"),
    "balkon": ("balkon",),
}
_ROOM_TITLES: dict[str, str] = {
    "mehmonxona": "Mehmonxona",
    "oshxona": "Oshxona",
    "yotoqxona": "Yotoqxona",
    "hammom": "Hammom",
    "bolalar xonasi": "Bolalar xonasi",
    "koridor": "Koridor",
    "terassa": "Terassa",
    "balkon": "Balkon",
}

# Words that signal an *explicit* catalog ask (a verb/noun), as opposed to a
# bare room/design noun that merely happens to be a catalog trigger.
_EXPLICIT_CATALOG_WORDS: frozenset[str] = frozenset(
    {
        "katalog",
        "katalok",
        "kataloq",
        "katalk",
        "katlog",
        "ktalog",
        "catalog",
        "rasm",
        "foto",
        "surat",
        "namuna",
        "namunala",
        "ko'rsat",
        "korsat",
        "koraylik",
        "tashla",
        "yubor",
        "dizayn",
        "dizaynlar",
        "variant",
        "variantlar",
        "portfolio",
        "misol",
        "model",
    }
)

# Phrases that must NEVER appear in a generated reply.
_FORBIDDEN_REPLY_SUBSTRINGS: tuple[str, ...] = (
    "aniq narx",
    "final narx",
    "100%",
    "100 %",
    "bugun kelamiz",
    "bugun qilamiz",
    "bugun keladi",
    "darhol kelamiz",
    "hozir bog'lanadi",
    "hozir qo'ng'iroq",
    "yozib qo'ydim",
    "usta boradi",
    "eng arzon",
)


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CustomerConversationFacts:
    """Everything the agent knows about the customer at this turn."""

    design_key: str | None = None
    area_m2: float | None = None
    room_type: str | None = None
    district: str | None = None
    phone_present: bool = False
    wants_catalog: bool = False
    wants_price: bool = False
    wants_measurement: bool = False
    wants_operator: bool = False
    has_objection: bool = False
    objection_type: str | None = None
    warranty_question: bool = False
    stop_signal: bool = False
    last_user_message: str = ""
    conversation_stage: str = STAGE_GREETING
    lead_temperature: str = "cold"
    order_readiness_score: int = 0
    # Internal helpers (not in the minimum spec list, but harmless / useful).
    catalog_ambiguous: bool = False
    catalog_explicit: bool = False
    safety_risk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_key": self.design_key,
            "area_m2": self.area_m2,
            "room_type": self.room_type,
            "district": self.district,
            "phone_present": self.phone_present,
            "wants_catalog": self.wants_catalog,
            "wants_price": self.wants_price,
            "wants_measurement": self.wants_measurement,
            "wants_operator": self.wants_operator,
            "has_objection": self.has_objection,
            "objection_type": self.objection_type,
            "warranty_question": self.warranty_question,
            "stop_signal": self.stop_signal,
            "last_user_message": self.last_user_message,
            "conversation_stage": self.conversation_stage,
            "lead_temperature": self.lead_temperature,
            "order_readiness_score": self.order_readiness_score,
        }


@dataclass(frozen=True)
class MissingInfo:
    """Which order-relevant facts are still unknown."""

    fields: tuple[str, ...] = ()

    @property
    def has_all(self) -> bool:
        return len(self.fields) == 0

    def __contains__(self, item: str) -> bool:
        return item in self.fields


@dataclass(frozen=True)
class SalesDialogueQuestion:
    """A single, warm, human-like question to ask next."""

    field: str  # which fact this question collects ("" if not a fact-collector)
    text: str


@dataclass(frozen=True)
class SalesDialogueDecision:
    """The agent's chosen move for this turn."""

    intent: str
    confidence: float
    should_answer: bool
    should_ask_question: bool
    question_text: str
    next_action: str
    reason: str
    order_readiness_score: int
    missing_fields: tuple[str, ...]
    safety_note: str = ""


@dataclass(frozen=True)
class SalesDialoguePlan:
    """Top-level bundle: facts + decision + missing-info for one turn."""

    facts: CustomerConversationFacts
    missing: MissingInfo
    decision: SalesDialogueDecision
    reply_text: str = ""
    questions_asked: int = field(default=0)


# ── Phase 3: fact extraction (memory adapter) ───────────────────────────────


def _detect_room(text_lower: str) -> str | None:
    for canonical, syns in _ROOM_MAP.items():
        for syn in syns:
            if syn in text_lower:
                return canonical
    return None


def _detect_design_key(text: str, combo: dict[str, Any]) -> str | None:
    """Resolve a PriceCalculator-style design key from the message.

    Uses parse_combo's clean design first (no room bleed), then the
    price-only aliases (``oddiy`` etc.)."""
    display = combo.get("design")
    if display and display in _DESIGN_DISPLAY_TO_KEY:
        return _DESIGN_DISPLAY_TO_KEY[display]
    lower = text.lower()
    for alias in sorted(_EXTRA_DESIGN_ALIASES, key=len, reverse=True):
        if alias in lower:
            return _EXTRA_DESIGN_ALIASES[alias]
    return None


def _has_phone(text: str, state_data: dict[str, Any]) -> bool:
    if state_data.get("price_phone") or state_data.get("phone_captured"):
        return True
    try:
        from shared.utils.phone import extract_phone_from_text

        return extract_phone_from_text(text) is not None
    except Exception:
        return False


def _as_facts_dict(prev: Any) -> dict[str, Any]:
    if prev is None:
        return {}
    if isinstance(prev, CustomerConversationFacts):
        return prev.to_dict()
    if isinstance(prev, dict):
        return dict(prev)
    return {}


def extract_facts(
    text: str,
    state_data: dict[str, Any] | None = None,
    previous_facts: Any = None,
) -> CustomerConversationFacts:
    """Build :class:`CustomerConversationFacts` from the current message,
    the FSM state dict, and any previously known facts.

    Sticky *slots* (design / area / room / district / phone) carry forward;
    *intent* flags (wants_price, …) reflect only the current message.
    """
    text = text or ""
    state_data = state_data or {}
    prev = _as_facts_dict(previous_facts)
    lower_raw = text.lower()
    latin = latinize_uz_cyrillic(text)

    # ── Slots: previous → FSM → current message (current wins) ──────────
    combo = parse_combo(text)

    # Current-message contributions (used for sticky-flow continuation).
    cur_design = _detect_design_key(text, combo)
    cur_area = combo.get("area")

    design_key = cur_design or state_data.get("price_design") or prev.get("design_key")
    area_m2 = combo.get("area")
    if area_m2 is None:
        area_m2 = state_data.get("price_area") or prev.get("area_m2")
    room_type = _detect_room(lower_raw) or state_data.get("price_room") or prev.get("room_type")
    district = combo.get("district") or state_data.get("price_district") or prev.get("district")
    phone_present = _has_phone(text, state_data) or bool(prev.get("phone_present"))

    # ── Intent flags: current message only ─────────────────────────────
    stop_signal = FollowupSchedulerService.is_stop_signal(text) or (
        FollowupSchedulerService.is_stop_signal(latin)
    )
    safety_risk = detect_prompt_injection(text)
    wants_measurement = _is_measurement_request(text)
    wants_operator = _is_operator_request(text)

    price_intent = _is_price_query(text) or _is_price_query(latin) or combo.get("area") is not None
    warranty_question = _is_warranty_quality_question(text)

    cat_result = resolve_catalog_link(text)
    catalog_ambiguous = bool(cat_result.needs_confirmation)
    wants_catalog = _is_catalog_request(text) and not price_intent
    catalog_explicit = any(w in lower_raw or w in latin for w in _EXPLICIT_CATALOG_WORDS)

    obj = detect_objection_full(text)
    has_objection = obj is not None
    objection_type = obj.objection_type if obj else None

    # ── Sticky flow continuation: a bare fact-answer (phone / area /
    #    district) with no intent of its own inherits the prior turn's
    #    active flow so the agent keeps moving instead of re-clarifying.
    current_has_intent = any(
        [
            price_intent,
            wants_catalog,
            wants_measurement,
            wants_operator,
            has_objection,
            warranty_question,
            stop_signal,
            safety_risk,
        ]
    )
    _blocking_intent = (
        wants_measurement
        or wants_operator
        or has_objection
        or warranty_question
        or stop_signal
        or safety_risk
    )
    if prev:
        # Continue an active PRICE flow when the user supplies a needed slot
        # (design / area). Design names double as catalog triggers, so prior
        # price intent + a slot answer + no explicit catalog verb = price.
        if (
            prev.get("wants_price")
            and (cur_design is not None or cur_area is not None)
            and not catalog_explicit
            and not _blocking_intent
        ):
            price_intent = True
        # Continue an active flow on a bare fact-answer with no own intent
        # (e.g. a phone / district reply during a measurement flow).
        if not current_has_intent:
            if prev.get("wants_measurement"):
                wants_measurement = True
            if prev.get("wants_price"):
                price_intent = True

    facts = CustomerConversationFacts(
        design_key=design_key,
        area_m2=area_m2,
        room_type=room_type,
        district=district,
        phone_present=phone_present,
        wants_catalog=wants_catalog,
        wants_price=price_intent,
        wants_measurement=wants_measurement,
        wants_operator=wants_operator,
        has_objection=has_objection,
        objection_type=objection_type,
        warranty_question=warranty_question,
        stop_signal=stop_signal,
        last_user_message=text[:200],
        catalog_ambiguous=catalog_ambiguous,
        catalog_explicit=catalog_explicit,
        safety_risk=safety_risk,
    )

    readiness = compute_order_readiness(facts)
    stage = _derive_stage(facts)
    temperature = _derive_temperature(readiness, facts)
    return replace(
        facts,
        order_readiness_score=readiness,
        conversation_stage=stage,
        lead_temperature=temperature,
    )


# ── Missing info + readiness ─────────────────────────────────────────────────


def compute_missing_info(facts: CustomerConversationFacts) -> MissingInfo:
    """Order-relevant facts still unknown (room is *not* required for an order)."""
    missing: list[str] = []
    if facts.design_key is None:
        missing.append("design_key")
    if facts.area_m2 is None:
        missing.append("area_m2")
    if facts.district is None:
        missing.append("district")
    if not facts.phone_present:
        missing.append("phone_present")
    return MissingInfo(fields=tuple(missing))


def compute_order_readiness(facts: CustomerConversationFacts) -> int:
    """0-100, monotonically increasing as facts accumulate."""
    score = 0
    if facts.design_key is not None:
        score += _READINESS_WEIGHTS["design_key"]
    if facts.area_m2 is not None:
        score += _READINESS_WEIGHTS["area_m2"]
    if facts.room_type is not None:
        score += _READINESS_WEIGHTS["room_type"]
    if facts.district is not None:
        score += _READINESS_WEIGHTS["district"]
    if facts.phone_present:
        score += _READINESS_WEIGHTS["phone_present"]
    return min(100, score)


def _derive_stage(facts: CustomerConversationFacts) -> str:
    if facts.stop_signal:
        return STAGE_STOPPED
    if facts.wants_operator:
        return STAGE_HANDOFF
    if facts.phone_present:
        return STAGE_CLOSING
    if facts.has_objection:
        return STAGE_OBJECTION
    if facts.wants_price or (facts.area_m2 is not None and facts.design_key is not None):
        return STAGE_PRICING
    if facts.wants_catalog:
        return STAGE_CATALOG
    if facts.design_key or facts.area_m2 or facts.room_type or facts.district:
        return STAGE_DISCOVERY
    return STAGE_GREETING


def _derive_temperature(readiness: int, facts: CustomerConversationFacts) -> str:
    if facts.phone_present or readiness >= 60:
        return "hot"
    if readiness >= 30 or facts.wants_measurement or facts.wants_price:
        return "warm"
    return "cold"


# ── Phase 2: decision rules ──────────────────────────────────────────────────


def decide(facts: CustomerConversationFacts) -> SalesDialogueDecision:
    """Choose the single best next action. Priority order is fixed:

    stop > safety > operator > measurement > objection > price > warranty
    > catalog > room-only > clarify.
    """
    missing = compute_missing_info(facts)
    readiness = facts.order_readiness_score

    def _d(
        *,
        intent: str,
        action: str,
        reason: str,
        confidence: float,
        ask: bool,
        question: str = "",
        answer: bool = False,
        safety_note: str = "",
    ) -> SalesDialogueDecision:
        return SalesDialogueDecision(
            intent=intent,
            confidence=confidence,
            should_answer=answer,
            should_ask_question=ask,
            question_text=question if ask else "",
            next_action=action,
            reason=reason,
            order_readiness_score=readiness,
            missing_fields=missing.fields,
            safety_note=safety_note,
        )

    # 1. Stop always wins.
    if facts.stop_signal:
        return _d(
            intent=INTENT_STOP,
            action=POLITE_STOP,
            reason="stop_signal",
            confidence=0.99,
            ask=False,
            answer=True,
            safety_note="honour_opt_out",
        )

    # 2. Safety always wins.
    if facts.safety_risk:
        return _d(
            intent=INTENT_SAFETY,
            action=SAFETY_BLOCK,
            reason="prompt_injection",
            confidence=0.99,
            ask=False,
            answer=True,
            safety_note="injection_blocked_no_leak",
        )

    # 3. Explicit operator request wins over general AI.
    if facts.wants_operator:
        return _d(
            intent=INTENT_OPERATOR,
            action=CREATE_HANDOFF,
            reason="operator_requested",
            confidence=0.9,
            ask=False,
            answer=True,
            safety_note="no_eta_promise",
        )

    # 4. Measurement / order intent → collect contact, then offer.
    if facts.wants_measurement:
        if not facts.phone_present:
            return _d(
                intent=INTENT_MEASUREMENT,
                action=ASK_PHONE,
                reason="measurement_needs_phone",
                confidence=0.9,
                ask=True,
                question=ASK_PHONE,
            )
        if facts.district is None:
            return _d(
                intent=INTENT_MEASUREMENT,
                action=ASK_DISTRICT,
                reason="measurement_needs_district",
                confidence=0.9,
                ask=True,
                question=ASK_DISTRICT,
            )
        return _d(
            intent=INTENT_MEASUREMENT,
            action=OFFER_MEASUREMENT,
            reason="measurement_ready",
            confidence=0.92,
            ask=False,
            answer=True,
            safety_note="no_eta_promise",
        )

    # 5. Price intent → ask the missing piece, else answer.
    #    Checked before catalog/warranty so "gulli nech pul" → price, not catalog.
    #    Triggers on the CURRENT-message price signal only (``wants_price``
    #    already includes a freshly-parsed area); a *carried* area must not
    #    force every later turn into the price branch.
    if facts.wants_price:
        if facts.area_m2 is None:
            return _d(
                intent=INTENT_PRICE,
                action=ASK_AREA,
                reason="price_needs_area",
                confidence=0.85,
                ask=True,
                question=ASK_AREA,
            )
        if facts.design_key is None:
            return _d(
                intent=INTENT_PRICE,
                action=ASK_DESIGN,
                reason="price_needs_design",
                confidence=0.85,
                ask=True,
                question=ASK_DESIGN,
            )
        return _d(
            intent=INTENT_PRICE,
            action=ANSWER_PRICE,
            reason="price_ready",
            confidence=0.9,
            ask=False,
            answer=True,
            safety_note="estimate_only",
        )

    # 6. Warranty / quality FAQ → answer, then a soft next question.
    #    Wins over the objection rebuttal so a warranty question gets the
    #    informative FAQ (e.g. "kafolat bormi" → real 15-yil answer).
    if facts.warranty_question:
        return _d(
            intent=INTENT_WARRANTY,
            action=ANSWER_WARRANTY,
            reason="warranty_faq",
            confidence=0.85,
            ask=True,
            question="warranty_soft",
            answer=True,
        )

    # 7. Objection → calm handling.
    if facts.has_objection:
        return _d(
            intent=INTENT_OBJECTION,
            action=HANDLE_OBJECTION,
            reason=f"objection_{facts.objection_type}",
            confidence=0.85,
            ask=False,
            answer=True,
        )

    # 8. Catalog intent (after price/warranty/objection guards).
    if facts.wants_catalog:
        if facts.catalog_ambiguous:
            return _d(
                intent=INTENT_CATALOG,
                action=CLARIFY,
                reason="catalog_ambiguous",
                confidence=0.7,
                ask=True,
                question="catalog_confirm",
            )
        if facts.catalog_explicit or facts.design_key is not None:
            return _d(
                intent=INTENT_CATALOG,
                action=SEND_CATALOG,
                reason="catalog_request",
                confidence=0.85,
                ask=False,
                answer=True,
            )
        # else: only a bare room word triggered it → fall through to room rule.

    # 9. Room known but no explicit intent → move toward price.
    if facts.room_type is not None:
        return _d(
            intent=INTENT_PRICE,
            action=ASK_AREA,
            reason="room_known_offer_price",
            confidence=0.6,
            ask=True,
            question=ASK_AREA,
        )

    # 10. Unclear / nonsense → ONE simple clarification.
    return _d(
        intent=INTENT_CLARIFY,
        action=CLARIFY,
        reason="unclear",
        confidence=0.4,
        ask=True,
        question="clarify",
    )


# ── Phase 4: human-like response rendering ───────────────────────────────────


def _design_title(facts: CustomerConversationFacts) -> str:
    if facts.design_key and facts.design_key in _DESIGN_KEY_TITLES:
        return _DESIGN_KEY_TITLES[facts.design_key]
    return ""


def _room_title(facts: CustomerConversationFacts) -> str:
    if facts.room_type and facts.room_type in _ROOM_TITLES:
        return _ROOM_TITLES[facts.room_type]
    return ""


def _render_price_answer(facts: CustomerConversationFacts) -> str:
    """Delegate to the single source of truth for the taxminiy estimate."""
    if facts.area_m2 is None or facts.design_key is None:
        return "Maydon va turini bilsam, taxminiy narxni hisoblab beraman 🙂"
    try:
        svc = PriceCalculatorService()
        est = svc.calculate_estimate(facts.area_m2, facts.design_key)
        # build_user_response already says "taxminiy" and "Yakuniy narx
        # o'lchovdan keyin" — safe by construction.
        return svc.build_user_response(est)
    except Exception:
        return (
            "Maydon va turi bo'yicha taxminiy narxni tayyorlayman 🙂 "
            "Yakuniy narx o'lchovdan keyin aniqlanadi."
        )


def render_message(facts: CustomerConversationFacts, decision: SalesDialogueDecision) -> str:
    """Build the warm, short, Uzbek-Latin reply for the decided action.

    One primary question per turn, uses known facts, soft CTA, no robotic
    'intent detected' phrasing, never overpromises.
    """
    action = decision.next_action
    design = _design_title(facts)
    room = _room_title(facts)

    if action == POLITE_STOP:
        return "Tushunarli 😊 Bezovta qilmaymiz. Kerak bo'lsa, bemalol yozing."

    if action == SAFETY_BLOCK:
        return "Natijnoy potalok bo'yicha savolingiz bo'lsa, bemalol yozing! 😊"

    if action == CREATE_HANDOFF:
        return (
            "Albatta, operatorimizga ulayman 👨‍💼 Telefon raqamingizni qoldiring "
            "yoki savolingizni yozing — mutaxassis ko'rib chiqadi."
        )

    if action == ASK_PHONE:
        return (
            "Zo'r 🙂 Bepul o'lchovni kelishish uchun telefon raqamingizni yuboring 📞 "
            "(masalan: 90 123 45 67). Majburiyat yo'q."
        )

    if action == ASK_DISTRICT:
        base = "Qaysi tumandasiz? 📍"
        if facts.area_m2 is not None:
            return f"{base} Shunga qarab eng yaqin ustani yo'naltiramiz."
        return base

    if action == ASK_AREA:
        if design and room:
            return (
                f"{room} uchun {design} chiroyli chiqadi 😊 Maydoni taxminan nechchi m²? "
                "Masalan: 20 m² yoki 5x4."
            )
        if design:
            return (
                f"{design} bo'yicha hisoblab beraman 😊 Xonangiz taxminan nechchi m²? "
                "Masalan: 20 m² yoki 5x4."
            )
        if room:
            return (
                f"{room} uchun yordam beraman 😊 Maydoni taxminan nechchi m²? "
                "Shunga qarab taxminiy narxni aytaman."
            )
        return "Xonangiz taxminan nechchi m²? 🙂 Masalan: 20 m² yoki 5x4."

    if action == ASK_DESIGN:
        if facts.area_m2 is not None:
            return (
                f"{facts.area_m2:g} m² uchun qaysi turni tanlaymiz? 🙂 "
                "Masalan: Oddiy, Gulli, Hi-tech yoki Mramor."
            )
        return "Qaysi potolok turi yoqadi? 🙂 Oddiy, Gulli, Hi-tech, Mramor, Osmon yoki Qora UF."

    if action == ASK_ROOM:
        return "Qaysi xona uchun rejalashtiryapsiz? 🙂 Mehmonxona, oshxona, yotoqxona yoki hammom?"

    if action == ANSWER_PRICE:
        return _render_price_answer(facts)

    if action == SEND_CATALOG:
        if design:
            return f"{design} bo'yicha namunalarni ko'rsataman 😊 Pastdagi tugmadan oching 👇"
        return "Katalogimizda har xil xonalar uchun dizaynlar bor 😊 Pastdagi tugmadan ko'ring 👇"

    if action == ANSWER_WARRANTY:
        reply = _build_warranty_quality_reply(facts.last_user_message)
        soft = "\n\nXonangiz nechchi m² — taxminiy narxni ham aytib beraymi? 🙂"
        return reply + soft

    if action == HANDLE_OBJECTION:
        reply = _build_objection_reply(facts.objection_type or "expensive")
        if reply:
            return reply
        return (
            "Tushunaman 🙂 Sifat, toza montaj va 15 yil kafolat narxni oqlaydi. "
            "Maydoningiz nechchi m² — taxminiy hisobni ko'rsataymi?"
        )

    if action == OFFER_MEASUREMENT:
        return (
            "Rahmat 🙂 Ma'lumotlaringizni oldim. Mutaxassisimiz bog'lanib, "
            "bepul o'lchovni kelishadi."
        )

    # CLARIFY (catalog_confirm / clarify / unclear)
    if decision.question_text == "catalog_confirm":
        return "Siz qaysi dizaynni nazarda tutdingiz? 🙂 Masalan: Naqsh oq, Naqsh ramka yoki Qora naqsh?"
    return "Tushunolmadim 🙂 Narx hisoblaymizmi, katalog ko'rsataymi yoki bepul o'lchov kerakmi?"


# ── Top-level entry point ────────────────────────────────────────────────────


def plan_turn(
    text: str,
    state_data: dict[str, Any] | None = None,
    previous_facts: Any = None,
) -> SalesDialoguePlan:
    """Full single-turn plan: extract facts → decide → render.

    This is the one function the bot integration would call (behind the
    ``SALES_DIALOGUE_MANAGER_ENABLED`` flag). It performs no I/O.
    """
    facts = extract_facts(text, state_data, previous_facts)
    missing = compute_missing_info(facts)
    decision = decide(facts)
    reply = render_message(facts, decision)
    return SalesDialoguePlan(
        facts=facts,
        missing=missing,
        decision=decision,
        reply_text=reply,
        questions_asked=1 if decision.should_ask_question else 0,
    )


__all__ = [
    "CustomerConversationFacts",
    "MissingInfo",
    "SalesDialogueDecision",
    "SalesDialogueQuestion",
    "SalesDialoguePlan",
    "extract_facts",
    "compute_missing_info",
    "compute_order_readiness",
    "decide",
    "render_message",
    "plan_turn",
    "NEXT_ACTIONS",
]
