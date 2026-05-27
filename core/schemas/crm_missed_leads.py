"""Missed leads dashboard schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MissedLeadItem:
    contact_id: int = 0
    display_name: str = ""
    phone_masked: str | None = None
    lead_score: int = 0
    temperature: str = "cold"
    reason: str = ""
    severity: str = "medium"
    minutes_waiting: int = 0
    last_message_preview: str | None = None
    next_action: str = ""
    handoff_status: str | None = None


@dataclass
class MissedLeadSummary:
    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    hot_unanswered: int = 0
    operator_waiting: int = 0
    phone_shared_no_followup: int = 0
    avg_wait_minutes: int = 0
    oldest_wait_minutes: int = 0


@dataclass
class MissedLeadRecommendation:
    text: str = ""
    priority: str = "normal"
    count: int = 0


@dataclass
class MissedLeadDashboardResult:
    summary: MissedLeadSummary = field(default_factory=MissedLeadSummary)
    items: list[MissedLeadItem] = field(default_factory=list)
    recommendations: list[MissedLeadRecommendation] = field(
        default_factory=list,
    )
