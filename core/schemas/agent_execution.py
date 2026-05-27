"""Frozen dataclasses for agent execution sandbox."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentExecutionPayload:
    execution_id: str
    mode: str
    status: str
    action: str
    target_user_id: int | None = None
    channel: str = "none"
    message_text: str | None = None
    buttons: list[tuple[str, str]] | None = None
    admin_alert_text: str | None = None
    risk_level: str = "none"
    approval_required: bool = False
    approved_by: int | None = None
    blocked_reason: str | None = None
    rollback_action: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentExecutionResult:
    would_execute: bool
    blocked: bool
    blocked_reason: str | None = None
    requires_approval: bool = False
    mode: str = "log_only"
    risk_level: str = "none"
    safe_to_execute: bool = False
    status: str = "proposed"
    debug_trace: dict[str, object] = field(default_factory=dict)
