"""Frozen dataclasses for conversation policy engine output."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConversationPolicyContext:
    customer_state: str = "new_visitor"
    intent: str = "unclear"
    objection_type: str | None = None
    urgency: str = "low"
    lead_score: int = 0
    lead_temperature: str = "cold"
    followup_enabled: bool = True
    followup_count: int = 0
    lifetime_followup_count: int = 0
    has_phone: bool = False
    has_pending_followup: bool = False
    admin_escalation_cooldown_active: bool = False
    offer_type: str = "no_offer"
    ai_composer_enabled: bool = False
    dynamic_offer_enabled: bool = False


@dataclass(frozen=True)
class ConversationPolicyDecision:
    policy_action: str
    channel: str
    allowed: bool
    reason: str
    risk_level: str = "none"
    delay_minutes: int | None = None
    max_retries: int = 0
    should_use_ai_composer: bool = False
    should_use_dynamic_offer: bool = False
    should_notify_admin: bool = False
    should_cancel_pending: bool = False
    safety_flags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
