"""Frozen dataclasses for Stage 2 DRY_RUN observation report."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage2NoSendSafetyMetrics:
    actual_sent_count: int = 0
    executed_records_count: int = 0
    live_sender_executed: int = 0


@dataclass(frozen=True)
class Stage2PassFailResult:
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stage2DryRunReport:
    generated_at: str = ""
    since: str = ""
    until: str = ""
    environment: str = "unknown"
    duration_minutes: int = 0
    total_payloads: int = 0
    total_would_execute: int = 0
    total_blocked: int = 0
    action_counts: dict[str, int] = field(default_factory=dict)
    channel_counts: dict[str, int] = field(default_factory=dict)
    risk_counts: dict[str, int] = field(default_factory=dict)
    block_reason_counts: dict[str, int] = field(default_factory=dict)
    no_send: Stage2NoSendSafetyMetrics = field(default_factory=Stage2NoSendSafetyMetrics)
    health_status: str = "green"
    pass_fail: Stage2PassFailResult = field(default_factory=Stage2PassFailResult)
    recommendations: list[str] = field(default_factory=list)
