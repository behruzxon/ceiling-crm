"""Frozen dataclass for Stage 5 APPROVED_LIVE_SEND readiness gate."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stage5LiveSendReadinessResult:
    from_stage: str = "approval_required"
    to_stage: str = "approved_live_send"
    allowed: bool = False
    readiness_score: int = 0
    verdict: str = "not_ready"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""
