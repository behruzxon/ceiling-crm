"""Frozen dataclasses for Stage 1 observation report."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage1NoSendSafetyMetrics:
    followups_scheduled: int = 0
    followups_sent: int = 0
    admin_escalations_sent: int = 0
    execution_records_executed: int = 0
    live_sender_executed: int = 0


@dataclass(frozen=True)
class Stage1PassFailResult:
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stage1ObservationReport:
    generated_at: str = ""
    since: str = ""
    until: str = ""
    environment: str = "unknown"
    duration_minutes: int = 0
    total_users_observed: int = 0
    total_journey_events: int = 0
    total_orchestrator_traces: int = 0
    intent_counts: dict[str, int] = field(default_factory=dict)
    objection_counts: dict[str, int] = field(default_factory=dict)
    decision_state_counts: dict[str, int] = field(default_factory=dict)
    offer_type_counts: dict[str, int] = field(default_factory=dict)
    policy_action_counts: dict[str, int] = field(default_factory=dict)
    no_send: Stage1NoSendSafetyMetrics = field(
        default_factory=Stage1NoSendSafetyMetrics,
    )
    health_status: str = "green"
    pass_fail: Stage1PassFailResult = field(
        default_factory=Stage1PassFailResult,
    )
    recommendations: list[str] = field(default_factory=list)
