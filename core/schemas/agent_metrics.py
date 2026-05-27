"""Frozen dataclasses for agent metrics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JourneyMetrics:
    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    active_users: int = 0
    catalog_opened: int = 0
    price_calculated: int = 0
    order_started: int = 0
    phone_shared: int = 0
    operator_requested: int = 0


@dataclass(frozen=True)
class LeadMetrics:
    total_memories: int = 0
    hot_count: int = 0
    warm_count: int = 0
    cold_count: int = 0
    average_score: float = 0.0
    score_0_30: int = 0
    score_31_69: int = 0
    score_70_100: int = 0
    stopped_count: int = 0
    objection_counts: dict[str, int] = field(default_factory=dict)
    intent_counts: dict[str, int] = field(default_factory=dict)
    urgency_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class FollowupMetrics:
    total: int = 0
    pending: int = 0
    sent: int = 0
    cancelled: int = 0
    failed: int = 0
    skipped: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    due_count: int = 0
    average_per_user: float = 0.0


@dataclass(frozen=True)
class AdminEscalationMetrics:
    total: int = 0
    last_24h: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionMetrics:
    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_mode: dict[str, int] = field(default_factory=dict)
    pending_approval: int = 0
    expired: int = 0
    blocked: int = 0
    high_risk_blocked: int = 0
    block_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SafetyMetrics:
    stop_signals: int = 0
    policy_blocked: int = 0
    sandbox_blocked: int = 0
    daily_cap_blocks: int = 0
    lifetime_cap_blocks: int = 0


@dataclass(frozen=True)
class AgentHealthMetrics:
    status: str = "green"
    pending_followups_due: int = 0
    failed_followups_24h: int = 0
    stale_followups: int = 0
    expired_approvals: int = 0
    execution_failures: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentMetricsOverview:
    journey: JourneyMetrics = field(default_factory=JourneyMetrics)
    leads: LeadMetrics = field(default_factory=LeadMetrics)
    followups: FollowupMetrics = field(default_factory=FollowupMetrics)
    escalations: AdminEscalationMetrics = field(default_factory=AdminEscalationMetrics)
    executions: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    safety: SafetyMetrics = field(default_factory=SafetyMetrics)
    health: AgentHealthMetrics = field(default_factory=AgentHealthMetrics)
