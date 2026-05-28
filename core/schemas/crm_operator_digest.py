"""Operator daily digest schemas — pure dataclasses, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OperatorDigestMetric:
    """Single metric value (used for compact lists)."""

    label: str = ""
    value: int = 0
    severity: str = "info"


@dataclass
class OperatorDigestItem:
    """Detailed metric row rendered in the digest body."""

    metric_key: str = ""
    label: str = ""
    value: int | float | str = 0
    severity: str = "info"
    note: str | None = None


@dataclass
class OperatorDigestRecommendation:
    """A prioritized operator instruction."""

    rank: int = 0
    text: str = ""
    severity: str = "info"


@dataclass
class OperatorWorkloadEntry:
    """Per-operator workload row used inside the digest."""

    operator_id: str = "unassigned"
    assigned_open: int = 0
    urgent_assigned: int = 0
    oldest_assigned_minutes: int = 0


@dataclass
class OperatorDigestSummary:
    """Top-line digest counters + overall severity."""

    severity: str = "green"
    total_open: int = 0
    waiting_phone: int = 0
    assigned: int = 0
    contacted_today: int = 0
    resolved_today: int = 0
    expired_today: int = 0
    urgent_open: int = 0
    high_open: int = 0
    oldest_wait_minutes: int = 0
    total_missed: int = 0
    critical_missed: int = 0
    high_missed: int = 0
    hot_unanswered: int = 0
    operator_waiting: int = 0
    phone_shared_no_followup: int = 0


@dataclass
class OperatorDigestResult:
    """Full digest payload returned by the service."""

    summary: OperatorDigestSummary = field(default_factory=OperatorDigestSummary)
    metrics: list[OperatorDigestItem] = field(default_factory=list)
    recommendations: list[OperatorDigestRecommendation] = field(default_factory=list)
    workload: list[OperatorWorkloadEntry] = field(default_factory=list)
    generated_at: datetime | None = None
