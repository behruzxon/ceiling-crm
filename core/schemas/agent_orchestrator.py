"""Frozen dataclasses for agent response orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentResponsePayload:
    action: str
    source: str
    allowed: bool
    reason: str
    user_message_text: str | None = None
    user_buttons: list[tuple[str, str]] | None = None
    admin_alert_text: str | None = None
    admin_buttons: list[tuple[str, str]] | None = None
    followup_type: str | None = None
    delay_minutes: int | None = None
    cancel_pending: bool = False
    disable_agent: bool = False
    should_commit_memory: bool = True
    safety_flags: list[str] = field(default_factory=list)
    debug_trace: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
