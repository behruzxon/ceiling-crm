"""Simulation runner — executes a scenario through the full agent pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.services.agent_response_orchestrator import AgentResponseOrchestrator
from core.services.conversation_policy_service import ConversationPolicyService
from core.services.dynamic_offer_service import DynamicOfferService
from core.services.lead_signal_service import LeadSignalService


@dataclass
class ScenarioResult:
    signal_intent: str = "unclear"
    signal_objection: str | None = None
    signal_urgency: str = "low"
    signal_area: float | None = None
    offer_type: str = "no_offer"
    offer_cta: str = "wait"
    policy_action: str = "wait_and_observe"
    policy_channel: str = "internal_only"
    policy_allowed: bool = True
    policy_risk: str = "none"
    orch_action: str = "store_memory_only"
    orch_allowed: bool = True
    orch_user_text: str | None = None
    orch_admin_text: str | None = None
    orch_cancel_pending: bool = False
    orch_disable_agent: bool = False
    safety_flags: list[str] = field(default_factory=list)


def build_memory(
    *,
    intent: str = "unclear",
    objection: str | None = None,
    urgency: str = "low",
    lead_score: int = 0,
    temp: str = "cold",
    followup_enabled: bool = True,
    followup_count: int = 0,
    phone: bool = False,
    area: float | None = None,
    state: str = "new_visitor",
    has_pending: bool = False,
    admin_cooldown: bool = False,
) -> dict[str, Any]:
    md: dict[str, Any] = {
        "last_intent": intent,
        "urgency": urgency,
        "lead_score": lead_score,
        "customer_state": state,
    }
    if objection:
        md["objection_type"] = objection
    if has_pending:
        md["has_pending_followup"] = True
    if admin_cooldown:
        md["admin_escalation_cooldown_active"] = True
    m: dict[str, Any] = {
        "lead_temperature": temp,
        "followup_enabled": followup_enabled,
        "followup_count": followup_count,
        "memory_data": md,
        "telegram_user_id": 99999,
    }
    if phone:
        m["phone_masked"] = "+998**…**00"
    if area:
        m["area_m2"] = area
    return m


def run_scenario(
    text: str | None = None,
    memory: dict[str, Any] | None = None,
    source: str = "user_message",
    followup_type: str | None = None,
    events: list[dict[str, Any]] | None = None,
) -> ScenarioResult:
    mem = memory or build_memory()
    result = ScenarioResult()

    if text:
        sig = LeadSignalService.extract_signals(text)
        result.signal_intent = sig.intent
        result.signal_objection = sig.objection_type
        result.signal_urgency = sig.urgency
        result.signal_area = sig.area_m2

    offer = DynamicOfferService.choose_offer(
        memory=mem,
        lead_signal={"intent": result.signal_intent, "objection_type": result.signal_objection,
                     "urgency": result.signal_urgency} if text else None,
        recent_events=events or [],
    )
    result.offer_type = offer.offer_type
    result.offer_cta = offer.cta

    signal_dict = {
        "intent": result.signal_intent,
        "objection_type": result.signal_objection,
        "urgency": result.signal_urgency,
    } if text else {}

    policy = ConversationPolicyService.evaluate(
        memory=mem,
        decision={},
        offer={"offer_type": offer.offer_type, "cta": offer.cta},
        lead_signal=signal_dict or None,
    )
    result.policy_action = policy.policy_action
    result.policy_channel = policy.channel
    result.policy_allowed = policy.allowed
    result.policy_risk = policy.risk_level

    payload = AgentResponseOrchestrator.run_pipeline(
        memory=mem,
        text=text,
        source=source,
        followup_type=followup_type,
    )
    result.orch_action = payload.action
    result.orch_allowed = payload.allowed
    result.orch_user_text = payload.user_message_text
    result.orch_admin_text = payload.admin_alert_text
    result.orch_cancel_pending = payload.cancel_pending
    result.orch_disable_agent = payload.disable_agent
    result.safety_flags = payload.safety_flags

    return result
