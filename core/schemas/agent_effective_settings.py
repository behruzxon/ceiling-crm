"""Frozen dataclasses for agent effective settings snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentFollowupSettings:
    enabled: bool = False
    catalog_enabled: bool = False
    price_enabled: bool = False
    order_enabled: bool = False
    catalog_delay_minutes: int = 10
    price_delay_minutes: int = 10
    order_delay_minutes: int = 10
    max_daily_per_user: int = 3


@dataclass(frozen=True)
class AgentAIComposerSettings:
    enabled: bool = False
    model: str = "gpt-4o-mini"
    timeout_seconds: int = 8
    max_tokens: int = 180


@dataclass(frozen=True)
class AgentDecisionSettings:
    decision_enabled: bool = False
    lead_signal_enabled: bool = False
    lead_scoring_enabled: bool = False
    dynamic_offer_enabled: bool = False
    conversation_policy_enabled: bool = False
    min_confidence: int = 60


@dataclass(frozen=True)
class AgentExecutionSettings:
    sandbox_enabled: bool = False
    execution_mode: str = "log_only"
    queue_enabled: bool = False
    api_approval_enabled: bool = False
    live_sender_enabled: bool = False
    auto_execute_approved: bool = False
    batch_limit: int = 10
    daily_cap: int = 3


@dataclass(frozen=True)
class AgentOrchestratorSettings:
    enabled: bool = False
    log_only: bool = True
    min_confidence: int = 60
    trace_enabled: bool = True


@dataclass(frozen=True)
class AgentAdminEscalationSettings:
    enabled: bool = False
    after_followups: int = 2
    cooldown_minutes: int = 60


@dataclass(frozen=True)
class SettingSource:
    key: str
    value: object
    source: str = "default"


@dataclass(frozen=True)
class AgentEffectiveSettingsSnapshot:
    followup: AgentFollowupSettings = field(default_factory=AgentFollowupSettings)
    ai_composer: AgentAIComposerSettings = field(default_factory=AgentAIComposerSettings)
    decision: AgentDecisionSettings = field(default_factory=AgentDecisionSettings)
    execution: AgentExecutionSettings = field(default_factory=AgentExecutionSettings)
    orchestrator: AgentOrchestratorSettings = field(default_factory=AgentOrchestratorSettings)
    escalation: AgentAdminEscalationSettings = field(default_factory=AgentAdminEscalationSettings)
    sources: list[SettingSource] = field(default_factory=list)
