"""Price calculator schemas — frozen dataclasses for deterministic pricing."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriceEstimateResult:
    area_m2: float
    design_key: str
    design_title: str
    rate_uzs_per_m2: int
    subtotal_uzs: int
    discount_percent: float = 0.0
    discount_amount_uzs: int = 0
    total_uzs: int = 0
    is_estimate: bool = True
    source: str = "customer_facing"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceClarificationResult:
    needs_area: bool = False
    needs_design: bool = False
    question: str = ""
    parsed_area: float | None = None
    parsed_design: str | None = None


@dataclass(frozen=True)
class PriceCalculatorResponse:
    estimate: PriceEstimateResult | None = None
    clarification: PriceClarificationResult | None = None
    user_text: str = ""
    memory_payload: dict | None = None
