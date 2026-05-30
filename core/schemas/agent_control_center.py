"""Frozen dataclasses for agent control center."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentFeatureFlagStatus:
    name: str
    enabled: bool
    stage: str = ""
    risk: str = "none"


@dataclass(frozen=True)
class AgentRolloutStageStatus:
    stage: str = "off"
    label: str = "OFF"
    description: str = ""


@dataclass(frozen=True)
class AgentPreflightStatus:
    status: str = "green"
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentCanaryStatus:
    mode: str = "log_only"
    canary_user_count: int = 0
    approval_required: bool = False
    auto_execute: bool = False
    batch_limit: int = 10
    daily_cap: int = 3


@dataclass(frozen=True)
class AgentSafetySummary:
    status: str = "green"
    dangerous_combos: list[str] = field(default_factory=list)
    missing_configs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentControlCenterSnapshot:
    rollout_stage: AgentRolloutStageStatus = field(
        default_factory=AgentRolloutStageStatus,
    )
    preflight: AgentPreflightStatus = field(
        default_factory=AgentPreflightStatus,
    )
    canary: AgentCanaryStatus = field(default_factory=AgentCanaryStatus)
    safety: AgentSafetySummary = field(default_factory=AgentSafetySummary)
    flags: list[AgentFeatureFlagStatus] = field(default_factory=list)
    health_status: str = "green"


@dataclass(frozen=True)
class AgentLastDecisionView:
    decision_id: str = ""
    timestamp: str = ""
    intent: str = ""
    safety_flags: tuple[str, ...] = ()
    execution_mode: str = ""


@dataclass(frozen=True)
class AgentControlSummary:
    engine_on: bool = False
    log_only: bool = False
    live_send_safe: bool = True
    status_pill_label: str = "ENGINE OFF"
    status_pill_color: str = "gray"
    safe_text: str = ""
    last_decision: AgentLastDecisionView | None = None
    empty_state_text: str = (
        "Hali agent qarorlari yo'q. LOG_ONLY yoqilganda qarorlar shu yerda ko'rinadi."
    )
