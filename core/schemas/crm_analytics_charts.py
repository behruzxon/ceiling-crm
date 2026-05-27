"""Analytics chart schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChartPoint:
    label: str = ""
    value: int = 0
    color: str = "#4f46e5"


@dataclass
class ChartSeries:
    title: str = ""
    points: list[ChartPoint] = field(default_factory=list)
    total: int = 0


@dataclass
class AnalyticsDashboardCharts:
    lead_temperature: ChartSeries = field(default_factory=ChartSeries)
    intent_breakdown: ChartSeries = field(default_factory=ChartSeries)
    missed_severity: ChartSeries = field(default_factory=ChartSeries)
    handoff_status: ChartSeries = field(default_factory=ChartSeries)
    top_districts: ChartSeries = field(default_factory=ChartSeries)
    top_ceiling_types: ChartSeries = field(default_factory=ChartSeries)
