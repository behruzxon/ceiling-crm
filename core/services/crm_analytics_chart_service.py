"""Analytics chart builder — pure functions, no DB I/O."""
from __future__ import annotations

from typing import Any

from core.schemas.crm_analytics_charts import (
    AnalyticsDashboardCharts,
    ChartPoint,
    ChartSeries,
)

TEMPERATURE_COLORS = {"hot": "#ef4444", "warm": "#f59e0b", "cold": "#3b82f6"}
SEVERITY_COLORS = {
    "critical": "#dc2626",
    "high": "#f59e0b",
    "medium": "#3b82f6",
    "low": "#94a3b8",
}
HANDOFF_COLORS = {
    "open": "#f59e0b",
    "waiting_phone": "#3b82f6",
    "assigned": "#8b5cf6",
    "contacted": "#10b981",
    "resolved": "#059669",
    "cancelled": "#94a3b8",
}
INTENT_COLORS = {
    "price_interest": "#4f46e5",
    "operator_requested": "#f59e0b",
    "catalog_viewed": "#10b981",
    "order_started": "#059669",
    "measurement_requested": "#8b5cf6",
}
MAX_TOP_ITEMS = 10


def build_temperature_chart(
    counts: dict[str, int] | None = None,
) -> ChartSeries:
    data = counts or {}
    points = [
        ChartPoint(
            label=k.title(),
            value=data.get(k, 0),
            color=TEMPERATURE_COLORS.get(k, "#94a3b8"),
        )
        for k in ("hot", "warm", "cold")
    ]
    return ChartSeries(
        title="Lead Temperature",
        points=points,
        total=sum(p.value for p in points),
    )


def build_intent_chart(
    counts: dict[str, int] | None = None,
) -> ChartSeries:
    data = counts or {}
    points = [
        ChartPoint(
            label=k.replace("_", " ").title(),
            value=data.get(k, 0),
            color=INTENT_COLORS.get(k, "#94a3b8"),
        )
        for k in INTENT_COLORS
    ]
    return ChartSeries(
        title="Intent Breakdown",
        points=points,
        total=sum(p.value for p in points),
    )


def build_missed_severity_chart(
    counts: dict[str, int] | None = None,
) -> ChartSeries:
    data = counts or {}
    points = [
        ChartPoint(
            label=k.title(),
            value=data.get(k, 0),
            color=SEVERITY_COLORS.get(k, "#94a3b8"),
        )
        for k in ("critical", "high", "medium", "low")
    ]
    return ChartSeries(
        title="Missed Leads Severity",
        points=points,
        total=sum(p.value for p in points),
    )


def build_handoff_chart(
    counts: dict[str, int] | None = None,
) -> ChartSeries:
    data = counts or {}
    points = [
        ChartPoint(
            label=k.replace("_", " ").title(),
            value=data.get(k, 0),
            color=HANDOFF_COLORS.get(k, "#94a3b8"),
        )
        for k in HANDOFF_COLORS
    ]
    return ChartSeries(
        title="Handoff Status",
        points=points,
        total=sum(p.value for p in points),
    )


def build_top_chart(
    items: list[tuple[str, int]],
    title: str = "Top",
) -> ChartSeries:
    limited = sorted(items, key=lambda x: x[1], reverse=True)[:MAX_TOP_ITEMS]
    points = [
        ChartPoint(label=name, value=count, color="#4f46e5")
        for name, count in limited
    ]
    return ChartSeries(
        title=title,
        points=points,
        total=sum(p.value for p in points),
    )


def build_all_charts(
    temperature: dict[str, int] | None = None,
    intents: dict[str, int] | None = None,
    missed_severity: dict[str, int] | None = None,
    handoff_status: dict[str, int] | None = None,
    districts: list[tuple[str, int]] | None = None,
    ceiling_types: list[tuple[str, int]] | None = None,
) -> AnalyticsDashboardCharts:
    return AnalyticsDashboardCharts(
        lead_temperature=build_temperature_chart(temperature),
        intent_breakdown=build_intent_chart(intents),
        missed_severity=build_missed_severity_chart(missed_severity),
        handoff_status=build_handoff_chart(handoff_status),
        top_districts=build_top_chart(
            districts or [], "Top Districts",
        ),
        top_ceiling_types=build_top_chart(
            ceiling_types or [], "Top Ceiling Types",
        ),
    )


def chart_series_to_dict(series: ChartSeries) -> dict[str, Any]:
    return {
        "title": series.title,
        "total": series.total,
        "points": [
            {"label": p.label, "value": p.value, "color": p.color}
            for p in series.points
        ],
    }
