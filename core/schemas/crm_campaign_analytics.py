"""Frozen dataclasses for CRM campaign analytics schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CRMCampaignDeliveryMetrics:
    total_attempts: int = 0
    proposed: int = 0
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    blocked_rate: float = 0.0
    unique_contacts: int = 0
    duplicate_blocked: int = 0


@dataclass(frozen=True)
class CRMCampaignBlockedReasonMetric:
    reason: str = ""
    count: int = 0


@dataclass(frozen=True)
class CRMCampaignFailureMetric:
    error_type: str = ""
    count: int = 0


@dataclass(frozen=True)
class CRMCampaignCanaryMetrics:
    canary_sent: int = 0
    canary_failed: int = 0
    non_canary_skipped: int = 0


@dataclass(frozen=True)
class CRMCampaignReplyMetrics:
    reply_count: int = 0
    reply_rate: float = 0.0
    contacts_replied: int = 0
    first_reply_avg_minutes: float = 0.0
    hot_replies: int = 0


@dataclass(frozen=True)
class CRMCampaignStatusChangeMetrics:
    status_changes: int = 0
    status_change_rate: float = 0.0
    by_status: list[tuple[str, int]] = field(default_factory=list)


@dataclass(frozen=True)
class CRMCampaignRecommendation:
    priority: str = "medium"
    title: str = ""
    description: str = ""


@dataclass(frozen=True)
class CRMCampaignAnalytics:
    campaign_id: int = 0
    delivery: CRMCampaignDeliveryMetrics = field(default_factory=CRMCampaignDeliveryMetrics)
    blocked_reasons: list[CRMCampaignBlockedReasonMetric] = field(default_factory=list)
    failure_reasons: list[CRMCampaignFailureMetric] = field(default_factory=list)
    canary: CRMCampaignCanaryMetrics = field(default_factory=CRMCampaignCanaryMetrics)
    replies: CRMCampaignReplyMetrics = field(default_factory=CRMCampaignReplyMetrics)
    status_changes: CRMCampaignStatusChangeMetrics = field(
        default_factory=CRMCampaignStatusChangeMetrics
    )
    recommendations: list[CRMCampaignRecommendation] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=True)
class CRMCampaignDashboardSummary:
    total_campaigns: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_blocked: int = 0
    overall_success_rate: float = 0.0
    overall_reply_rate: float = 0.0
    top_segments: list[tuple[str, int]] = field(default_factory=list)
