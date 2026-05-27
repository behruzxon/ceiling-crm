"""Frozen dataclasses for CRM dashboard analytics."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CRMFunnelStage:
    name: str = ""
    count: int = 0
    conversion_from_previous: float = 0.0
    conversion_from_total: float = 0.0

@dataclass(frozen=True)
class CRMMissedLeadMetrics:
    missed_lead_count: int = 0
    missed_hot_leads: int = 0
    missed_operator_requests: int = 0
    missed_phone_shared: int = 0
    missed_price_interested: int = 0

@dataclass(frozen=True)
class CRMDashboardAnalytics:
    generated_at: str = ""
    since: str = ""
    until: str = ""
    total_contacts: int = 0
    new_contacts: int = 0
    hot_leads: int = 0
    warm_leads: int = 0
    cold_leads: int = 0
    stopped: int = 0
    won: int = 0
    lost: int = 0
    unanswered_count: int = 0
    critical_count: int = 0
    overdue_count: int = 0
    avg_response_minutes: float = 0.0
    funnel: list[CRMFunnelStage] = field(default_factory=list)
    missed: CRMMissedLeadMetrics = field(default_factory=CRMMissedLeadMetrics)
    segment_counts: dict[str, int] = field(default_factory=dict)
    task_open: int = 0
    task_overdue: int = 0
    task_completed: int = 0
    task_completion_rate: float = 0.0
    top_intents: dict[str, int] = field(default_factory=dict)
    top_objections: dict[str, int] = field(default_factory=dict)
    top_locations: dict[str, int] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
