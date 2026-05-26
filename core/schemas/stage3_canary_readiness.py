"""Frozen dataclass for Stage 3 CANARY readiness gate."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage3CanaryReadinessResult:
    from_stage: str = "dry_run"
    to_stage: str = "canary"
    allowed: bool = False
    readiness_score: int = 0
    verdict: str = "not_ready"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""
