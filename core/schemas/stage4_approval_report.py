"""Frozen dataclasses for Stage 4 APPROVAL_REQUIRED observation report."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage4NoSendSafetyMetrics:
    executed_records_count: int = 0
    live_sender_executed: int = 0
    auto_execute_count: int = 0
    user_dm_sent_count: int = 0


@dataclass(frozen=True)
class Stage4PassFailResult:
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stage4ApprovalReport:
    generated_at: str = ""
    since: str = ""
    until: str = ""
    environment: str = "unknown"
    duration_minutes: int = 0
    total_proposals: int = 0
    proposed_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    expired_count: int = 0
    blocked_count: int = 0
    executed_count: int = 0
    pending_count: int = 0
    stale_pending_count: int = 0
    no_send: Stage4NoSendSafetyMetrics = field(default_factory=Stage4NoSendSafetyMetrics)
    health_status: str = "green"
    pass_fail: Stage4PassFailResult = field(default_factory=Stage4PassFailResult)
    recommendations: list[str] = field(default_factory=list)
