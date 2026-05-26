"""Frozen dataclass for lead signal extraction results."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeadSignalResult:
    intent: str
    objection_type: str | None
    urgency: str
    area_m2: float | None
    budget_amount: int | None
    lead_score_delta: int
    confidence_score: int
    detected_keywords: list[str] = field(default_factory=list)
    language: str = "uz"
    should_disable_followup: bool = False
    should_notify_admin: bool = False
    metadata: dict[str, object] = field(default_factory=dict)
