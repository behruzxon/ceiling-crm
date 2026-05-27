"""
core.services.agent_decision_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic rules engine that evaluates a customer's journey state and
recommends the next best action.  Pure function — no I/O, no side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.agent_decision import AgentDecision
from shared.constants.enums import (
    AgentActionType,
    AgentCustomerState,
    JourneyEventType,
)
from shared.logging import get_logger

log = get_logger(__name__)

_INACTIVE_WARM_HOURS = 24
_INACTIVE_COLD_HOURS = 72

_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        AgentCustomerState.STOPPED.value,
        AgentCustomerState.LOST.value,
        AgentCustomerState.CLOSED.value,
    }
)

_HIGH_IMPACT_ACTIONS: frozenset[str] = frozenset(
    {
        AgentActionType.ESCALATE_TO_ADMIN.value,
        AgentActionType.MARK_HOT_LEAD.value,
        AgentActionType.NOTIFY_ADMIN.value,
    }
)


def _event_set(events: list[dict[str, Any]]) -> frozenset[str]:
    return frozenset(e.get("event_type", "") for e in events)


def _has(events: frozenset[str], et: JourneyEventType) -> bool:
    return et.value in events


def _hours_since(dt: datetime | None) -> float:
    if dt is None:
        return 9999.0
    delta = datetime.now(UTC) - dt
    return max(delta.total_seconds() / 3600.0, 0.0)


def classify_customer_state(
    memory: dict[str, Any],
    event_types: frozenset[str],
) -> AgentCustomerState:
    if not memory.get("followup_enabled", True):
        sr = memory.get("stop_reason", "")
        if sr in ("deal_closed",):
            return AgentCustomerState.CLOSED
        if sr in ("lost_lead",):
            return AgentCustomerState.LOST
        return AgentCustomerState.STOPPED

    if _has(event_types, JourneyEventType.OPERATOR_REQUESTED):
        return AgentCustomerState.OPERATOR_HANDOFF

    if _has(event_types, JourneyEventType.PHONE_SHARED):
        return AgentCustomerState.PHONE_SHARED_HOT

    objection = memory.get("objection_type")
    if objection == "price":
        return AgentCustomerState.NEGOTIATING_PRICE

    # ── Signal-derived state from lead_signal_service ─────────────────
    md = memory.get("memory_data") or {}
    signal_intent = md.get("last_intent")
    signal_objection = md.get("objection_type")

    if signal_objection == "price" and objection != "price":
        return AgentCustomerState.NEGOTIATING_PRICE

    if signal_intent == "stop_request":
        return AgentCustomerState.STOPPED

    if signal_intent == "wants_operator":
        return AgentCustomerState.OPERATOR_HANDOFF

    if signal_intent == "wants_order":
        return AgentCustomerState.ORDER_INTENT

    if signal_intent == "wants_price":
        if memory.get("area_m2") or md.get("area_m2"):
            return AgentCustomerState.PRICE_CONSIDERING
        return AgentCustomerState.PRICE_CHECKING
    # ── End signal-derived state ──────────────────────────────────────

    if _has(event_types, JourneyEventType.ORDER_FORM_STARTED):
        if not _has(event_types, JourneyEventType.PHONE_SHARED):
            return AgentCustomerState.ORDER_ABANDONED
        return AgentCustomerState.ORDER_INTENT

    if _has(event_types, JourneyEventType.CLICKED_ORDER):
        return AgentCustomerState.ORDER_INTENT

    if _has(event_types, JourneyEventType.PRICE_CALCULATED):
        return AgentCustomerState.PRICE_CONSIDERING

    if _has(event_types, JourneyEventType.USED_PRICE_CALCULATOR):
        return AgentCustomerState.PRICE_CHECKING

    if _has(event_types, JourneyEventType.VIEWED_CATALOG_ITEM):
        return AgentCustomerState.DESIGN_INTERESTED

    if _has(event_types, JourneyEventType.OPENED_CATALOG):
        return AgentCustomerState.BROWSING_CATALOG

    if _has(event_types, JourneyEventType.STARTED_BOT):
        return AgentCustomerState.NEW_VISITOR

    temp = memory.get("lead_temperature", "cold")
    last_event_at = memory.get("last_event_at")
    if last_event_at is None:
        return AgentCustomerState.NEW_VISITOR
    hours = _hours_since(last_event_at)
    if hours >= _INACTIVE_COLD_HOURS:
        return AgentCustomerState.INACTIVE_COLD
    if hours >= _INACTIVE_WARM_HOURS and temp in ("warm", "hot"):
        return AgentCustomerState.INACTIVE_WARM

    return AgentCustomerState.NEW_VISITOR


_STATE_ACTION_MAP: dict[AgentCustomerState, tuple[AgentActionType, int]] = {
    AgentCustomerState.NEW_VISITOR: (AgentActionType.WAIT, 10),
    AgentCustomerState.BROWSING_CATALOG: (AgentActionType.SEND_CATALOG_FOLLOWUP, 40),
    AgentCustomerState.DESIGN_INTERESTED: (AgentActionType.SUGGEST_PRICE_CALCULATOR, 50),
    AgentCustomerState.PRICE_CHECKING: (AgentActionType.REQUEST_AREA, 45),
    AgentCustomerState.PRICE_CONSIDERING: (AgentActionType.SEND_PRICE_FOLLOWUP, 65),
    AgentCustomerState.ORDER_INTENT: (AgentActionType.REQUEST_PHONE, 70),
    AgentCustomerState.ORDER_ABANDONED: (AgentActionType.SEND_ORDER_FOLLOWUP, 80),
    AgentCustomerState.PHONE_SHARED_HOT: (AgentActionType.MARK_HOT_LEAD, 90),
    AgentCustomerState.OPERATOR_HANDOFF: (AgentActionType.DISABLE_FOLLOWUP, 85),
    AgentCustomerState.NEGOTIATING_PRICE: (AgentActionType.SUGGEST_OPERATOR, 70),
    AgentCustomerState.INACTIVE_WARM: (AgentActionType.ESCALATE_TO_ADMIN, 75),
    AgentCustomerState.INACTIVE_COLD: (AgentActionType.WAIT, 15),
    AgentCustomerState.STOPPED: (AgentActionType.WAIT, 0),
    AgentCustomerState.LOST: (AgentActionType.WAIT, 0),
    AgentCustomerState.CLOSED: (AgentActionType.WAIT, 0),
}

_FOLLOWUP_MAP: dict[AgentActionType, str] = {
    AgentActionType.SEND_CATALOG_FOLLOWUP: "catalog",
    AgentActionType.SEND_PRICE_FOLLOWUP: "price",
    AgentActionType.SEND_ORDER_FOLLOWUP: "abandoned_order",
}

_REASON_MAP: dict[AgentCustomerState, str] = {
    AgentCustomerState.NEW_VISITOR: "Yangi foydalanuvchi, hali harakat qilmagan",
    AgentCustomerState.BROWSING_CATALOG: "Katalog ko'ryapti, narx so'rash kerak",
    AgentCustomerState.DESIGN_INTERESTED: "Dizayn tanlamoqda, narx hisoblashga undash",
    AgentCustomerState.PRICE_CHECKING: "Kalkulyatorda, maydon kiritish kutilmoqda",
    AgentCustomerState.PRICE_CONSIDERING: "Narx oldi, buyurtma hali yo'q",
    AgentCustomerState.ORDER_INTENT: "Buyurtma niyati bor, telefon kerak",
    AgentCustomerState.ORDER_ABANDONED: "Buyurtma yarimta qoldi, eslatish kerak",
    AgentCustomerState.PHONE_SHARED_HOT: "Telefon yubordi — issiq lead!",
    AgentCustomerState.OPERATOR_HANDOFF: "Operator so'radi, follow-up to'xtatildi",
    AgentCustomerState.NEGOTIATING_PRICE: "Narx e'tirozi bor, operator taklif qilish",
    AgentCustomerState.INACTIVE_WARM: "Warm lead 24+ soat jim, admin eslatmasi kerak",
    AgentCustomerState.INACTIVE_COLD: "Sovuq lead, kutish",
    AgentCustomerState.STOPPED: "Foydalanuvchi to'xtaldi yoki rad etdi",
    AgentCustomerState.LOST: "Lead yo'qotilgan",
    AgentCustomerState.CLOSED: "Deal yopilgan",
}


def calculate_priority_score(
    memory: dict[str, Any],
    event_types: frozenset[str],
    base_priority: int,
) -> int:
    score = base_priority
    if memory.get("estimated_price"):
        score += 5
    if memory.get("phone_masked"):
        score += 10
    if memory.get("area_m2"):
        score += 3
    designs = memory.get("interested_designs") or []
    if len(designs) >= 2:
        score += 3
    temp = memory.get("lead_temperature", "cold")
    if temp == "hot":
        score += 10
    elif temp == "warm":
        score += 5
    md = memory.get("memory_data") or {}
    if md.get("urgency") == "high" and temp in ("warm", "hot"):
        score += 15
    return min(score, 100)


def calculate_confidence_score(
    memory: dict[str, Any],
    event_types: frozenset[str],
) -> int:
    signals = 0
    if event_types:
        signals += min(len(event_types), 5) * 8
    if memory.get("full_name"):
        signals += 5
    if memory.get("area_m2"):
        signals += 10
    if memory.get("estimated_price"):
        signals += 10
    if memory.get("phone_masked"):
        signals += 15
    if memory.get("district"):
        signals += 5
    designs = memory.get("interested_designs") or []
    if designs:
        signals += 5
    return min(signals, 100)


def evaluate(
    memory: dict[str, Any],
    recent_events: list[dict[str, Any]],
    now: datetime | None = None,
) -> AgentDecision:
    if now is None:
        now = datetime.now(UTC)

    et_set = _event_set(recent_events)
    state = classify_customer_state(memory, et_set)
    action, base_priority = _STATE_ACTION_MAP.get(
        state,
        (AgentActionType.WAIT, 0),
    )
    priority = calculate_priority_score(memory, et_set, base_priority)
    confidence = calculate_confidence_score(memory, et_set)
    reason = _REASON_MAP.get(state, "")
    temp = memory.get("lead_temperature", "cold")

    safety_flags: list[str] = []
    if not memory.get("followup_enabled", True):
        safety_flags.append("followup_disabled")
    fu_count = memory.get("followup_count", 0)
    if fu_count >= 5:
        safety_flags.append("lifetime_cap_reached")
    if memory.get("stop_reason"):
        safety_flags.append(f"stop:{memory['stop_reason']}")

    # Downgrade high-impact action on low confidence
    if action.value in _HIGH_IMPACT_ACTIONS and confidence < 60:
        action = AgentActionType.WAIT
        safety_flags.append("low_confidence_downgrade")

    # Prevent admin escalation for cold leads
    if action == AgentActionType.ESCALATE_TO_ADMIN and temp == "cold":
        action = AgentActionType.WAIT
        safety_flags.append("cold_lead_no_escalation")

    # Prevent any action on terminal states
    if state.value in _TERMINAL_STATES:
        action = AgentActionType.WAIT

    fu_type = _FOLLOWUP_MAP.get(action)
    should_fu = fu_type is not None and not safety_flags

    return AgentDecision(
        customer_state=state.value,
        action_type=action.value,
        priority_score=priority,
        confidence_score=confidence,
        reason=reason,
        lead_temperature=temp,
        admin_escalation_needed=action
        in (
            AgentActionType.ESCALATE_TO_ADMIN,
            AgentActionType.NOTIFY_ADMIN,
        ),
        should_schedule_followup=should_fu,
        followup_type=fu_type,
        delay_minutes=10 if should_fu else None,
        safety_flags=safety_flags,
    )


def evaluate_with_offer(
    memory: dict[str, Any],
    recent_events: list[dict[str, Any]],
    lead_signal: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[AgentDecision, DynamicOffer | None]:
    decision = evaluate(memory, recent_events, now=now)

    try:
        from shared.config import get_settings

        biz = get_settings().business
        if not biz.agent_dynamic_offer_enabled:
            return decision, None

        from core.services.dynamic_offer_service import DynamicOfferService

        offer = DynamicOfferService.choose_offer(
            memory=memory,
            lead_signal=lead_signal,
            recent_events=recent_events,
        )

        if offer.confidence_score < biz.agent_dynamic_offer_min_confidence:
            return decision, None

        return decision, offer
    except Exception:
        log.debug("dynamic_offer_generation_failed")
        return decision, None


def evaluate_full(
    memory: dict[str, Any],
    recent_events: list[dict[str, Any]],
    lead_signal: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[AgentDecision, DynamicOffer | None, ConversationPolicyDecision | None]:
    decision, offer = evaluate_with_offer(
        memory,
        recent_events,
        lead_signal=lead_signal,
        now=now,
    )

    try:
        from shared.config import get_settings

        biz = get_settings().business
        if not biz.agent_conversation_policy_enabled:
            return decision, offer, None

        from core.services.conversation_policy_service import ConversationPolicyService

        decision_dict = {
            "customer_state": decision.customer_state,
            "action_type": decision.action_type,
            "priority_score": decision.priority_score,
        }
        offer_dict = {"offer_type": offer.offer_type, "cta": offer.cta} if offer else {}
        signal_dict = lead_signal or {}

        policy = ConversationPolicyService.evaluate(
            memory=memory,
            decision=decision_dict,
            offer=offer_dict,
            lead_signal=signal_dict,
            recent_events=recent_events,
            now=now,
        )

        return decision, offer, policy
    except Exception:
        log.debug("conversation_policy_evaluation_failed")
        return decision, offer, None
