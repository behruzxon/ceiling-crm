"""Agent quality simulator schemas."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentScenario:
    text: str
    category: str  # price, objection, operator, catalog, order, multilingual, safety
    expected_intent: str | None = None
    expected_safety: str = "safe"  # safe, blocked, warning


@dataclass
class AgentScenarioResult:
    scenario: AgentScenario
    detected_intent: str | None = None
    design_parsed: str | None = None
    area_parsed: float | None = None
    objection_type: str | None = None
    objection_severity: str | None = None
    is_price_query: bool = False
    is_catalog_request: bool = False
    is_measurement_request: bool = False
    is_stop_signal: bool = False
    is_greeting: bool = False
    price_estimate_total: int | None = None
    clarification_needed: str | None = None
    safety_status: str = "safe"
    safety_violations: list[str] = field(default_factory=list)
    score: int = 0  # 1-5


@dataclass
class AgentQualityReport:
    total_scenarios: int = 0
    total_passed: int = 0
    total_failed: int = 0
    avg_score: float = 0.0
    safety_violations: int = 0
    category_scores: dict[str, float] = field(default_factory=dict)
    failed_scenarios: list[str] = field(default_factory=list)
