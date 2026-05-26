"""Frozen dataclasses for agent decision engine output."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentDecision:
    customer_state: str
    action_type: str
    priority_score: int
    confidence_score: int
    reason: str
    lead_temperature: str = "cold"
    admin_escalation_needed: bool = False
    should_schedule_followup: bool = False
    followup_type: str | None = None
    delay_minutes: int | None = None
    safety_flags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
