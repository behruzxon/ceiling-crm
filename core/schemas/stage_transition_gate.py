"""Frozen dataclasses for stage transition gate results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageTransitionGateResult:
    from_stage: str = "log_only"
    to_stage: str = "dry_run"
    allowed: bool = False
    readiness_score: int = 0
    verdict: str = "not_ready"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""
