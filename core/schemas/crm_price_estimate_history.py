"""Price estimate history schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PriceEstimateHistoryItem:
    estimate_id: str = ""
    contact_id: int = 0
    timestamp: str | None = None
    source: str = "unknown"
    area_m2: float = 0.0
    design_key: str = ""
    design_title: str = ""
    rate_uzs_per_m2: int = 0
    subtotal_uzs: int = 0
    discount_percent: float = 0.0
    discount_amount_uzs: int = 0
    total_uzs: int = 0
    is_estimate: bool = True
    warning: str = "Taxminiy hisob — yakuniy narx o'lchovdan keyin aniqlanadi"
    input_preview: str | None = None
    message_id: int | None = None
    handoff_after_estimate: bool = False
    operator_requested_after_estimate: bool = False
    metadata_summary: str | None = None


@dataclass
class PriceEstimateHistorySummary:
    total_estimates: int = 0
    latest_estimate_at: str | None = None
    latest_total_uzs: int = 0
    min_total_uzs: int = 0
    max_total_uzs: int = 0
    most_requested_design: str = ""
    total_area_m2: float = 0.0
    handoff_after_estimate_count: int = 0
    has_recent_estimate: bool = False


@dataclass
class PriceEstimateHistoryResult:
    contact_id: int = 0
    items: list[PriceEstimateHistoryItem] = field(default_factory=list)
    summary: PriceEstimateHistorySummary = field(
        default_factory=PriceEstimateHistorySummary,
    )
