"""Frozen dataclasses for Stage 3 CANARY observation report."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage3PublicSafetyMetrics:
    public_user_send_count: int = 0
    non_canary_allowed_count: int = 0
    high_risk_sent_count: int = 0
    critical_risk_sent_count: int = 0
    duplicate_sent_count: int = 0
    sensitive_leak_count: int = 0


@dataclass(frozen=True)
class Stage3PassFailResult:
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stage3CanaryReport:
    generated_at: str = ""
    since: str = ""
    until: str = ""
    environment: str = "unknown"
    duration_minutes: int = 0
    canary_user_count: int = 0
    canary_payload_count: int = 0
    canary_allowed_count: int = 0
    canary_blocked_count: int = 0
    non_canary_attempts: int = 0
    non_canary_blocked: int = 0
    block_reason_counts: dict[str, int] = field(default_factory=dict)
    risk_counts: dict[str, int] = field(default_factory=dict)
    public_safety: Stage3PublicSafetyMetrics = field(default_factory=Stage3PublicSafetyMetrics)
    health_status: str = "green"
    pass_fail: Stage3PassFailResult = field(default_factory=Stage3PassFailResult)
    recommendations: list[str] = field(default_factory=list)
