"""Frozen dataclass for Stage 4 APPROVAL_REQUIRED readiness gate."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage4ApprovalReadinessResult:
    from_stage: str = "canary"
    to_stage: str = "approval_required"
    allowed: bool = False
    readiness_score: int = 0
    verdict: str = "not_ready"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""
