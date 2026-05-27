"""Pydantic response schemas for the analytics API."""

from __future__ import annotations

from pydantic import BaseModel


class SourceStat(BaseModel):
    """Per-source lead performance."""

    source: str
    leads: int
    won: int
    lost: int
    rate: float


class BuyerTypeStat(BaseModel):
    """Per-buyer-type conversion stats (populated when Redis enrichment is available)."""

    type: str
    count: int
    won: int
    rate: float


class ObjectionStat(BaseModel):
    """Objection occurrence count."""

    type: str
    count: int


class ObjectionLostCorrelation(BaseModel):
    """Objection-to-lost-lead correlation."""

    type: str
    total: int
    lost: int
    lost_rate: float


class TacticStat(BaseModel):
    """Negotiation tactic effectiveness."""

    tactic: str
    count: int
    won: int
    rate: float


class StageStat(BaseModel):
    """Funnel stage count."""

    stage: str
    count: int


class FollowupStat(BaseModel):
    """Follow-up performance summary."""

    avg_followups_won: float
    avg_followups_lost: float
    avg_followups_all: float
    with_followup_pct: float


class FollowupTypeStat(BaseModel):
    """Per-follow-up-type stats."""

    type: str
    count: int
    won: int
    rate: float


class ScoreDistribution(BaseModel):
    """Lead score tier counts."""

    hot: int
    warm: int
    cold: int


class HealthDistribution(BaseModel):
    """Conversation health tier counts."""

    healthy: int
    at_risk: int
    critical: int


class SignalStat(BaseModel):
    """Conversation signal occurrence count."""

    signal: str
    count: int


class AutopilotActionStat(BaseModel):
    """Autopilot action type count."""

    action: str
    count: int


class ClosingReadinessDistribution(BaseModel):
    """Closing readiness tier counts."""

    NOT_READY: int
    NEAR_CLOSE: int
    READY_TO_CLOSE: int


class ClosingTacticStat(BaseModel):
    """Closing tactic count."""

    tactic: str
    count: int


class AnalyticsResponse(BaseModel):
    """Full sales analytics report for the web dashboard.

    Fields that require Redis AI memory enrichment (buyer_type_stats,
    top_objections, tactic_stats, conversation health, autopilot,
    auto-seller) will be empty/zero when only DB data is available.
    This is expected — the API currently provides DB-level analytics.
    """

    # ── Request metadata ───────────────────────────────────────────
    period: str
    days: int

    # ── Total summary ──────────────────────────────────────────────
    total_leads: int
    won_leads: int
    lost_leads: int
    active_leads: int
    conversion_rate: float

    # ── Source performance ─────────────────────────────────────────
    top_sources: list[SourceStat]

    # ── Buyer type conversion ──────────────────────────────────────
    buyer_type_stats: list[BuyerTypeStat]
    best_buyer_type: dict | None

    # ── Objection breakdown ────────────────────────────────────────
    top_objections: list[ObjectionStat]
    objection_severity_stats: dict
    objection_lost_correlation: list[ObjectionLostCorrelation]

    # ── Negotiation tactic effectiveness ───────────────────────────
    tactic_stats: list[TacticStat]
    best_tactic: dict | None

    # ── Funnel stages ──────────────────────────────────────────────
    stage_counts: list[StageStat]
    largest_dropoff_stage: str | None

    # ── Follow-up performance ──────────────────────────────────────
    followup_stats: FollowupStat
    best_followup_type: FollowupTypeStat | None
    followup_type_stats: list[FollowupTypeStat]

    # ── Score distribution ─────────────────────────────────────────
    score_distribution: ScoreDistribution
    avg_score: float

    # ── Revenue summary ────────────────────────────────────────────
    total_estimated_revenue: int
    avg_revenue_per_lead: int

    # ── Conversation health ────────────────────────────────────────
    avg_health_score: float
    health_distribution: HealthDistribution
    top_signals: list[SignalStat]
    cooling_count: int

    # ── Autopilot metrics ──────────────────────────────────────────
    autopilot_action_distribution: list[AutopilotActionStat]
    opportunity_count: int
    at_risk_count: int
    closing_ready_count: int

    # ── Closing readiness ──────────────────────────────────────────
    closing_readiness_distribution: ClosingReadinessDistribution
    close_opportunity_count: int
    close_loss_risk_count: int
    closing_tactic_distribution: list[ClosingTacticStat]

    # ── Auto-seller ────────────────────────────────────────────────
    auto_reply_count: int
    auto_escalation_count: int
    auto_reply_confidence_avg: float

    # ── Recommendations ────────────────────────────────────────────
    recommendations: list[str]
