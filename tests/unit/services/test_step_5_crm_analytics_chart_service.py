"""Tests for Step 5 — Analytics Chart Service."""

from __future__ import annotations

from core.schemas.crm_analytics_charts import (
    AnalyticsDashboardCharts,
    ChartPoint,
    ChartSeries,
)
from core.services.crm_analytics_chart_service import (
    MAX_TOP_ITEMS,
    build_all_charts,
    build_handoff_chart,
    build_intent_chart,
    build_missed_severity_chart,
    build_temperature_chart,
    build_top_chart,
    chart_series_to_dict,
)


class TestChartPoint:
    def test_defaults(self):
        p = ChartPoint()
        assert p.label == ""
        assert p.value == 0

    def test_custom(self):
        p = ChartPoint(label="Hot", value=10, color="#ff0000")
        assert p.label == "Hot"


class TestChartSeries:
    def test_defaults(self):
        s = ChartSeries()
        assert s.total == 0
        assert len(s.points) == 0


class TestTemperatureChart:
    def test_empty(self):
        s = build_temperature_chart()
        assert s.total == 0
        assert len(s.points) == 3

    def test_with_data(self):
        s = build_temperature_chart({"hot": 5, "warm": 10, "cold": 20})
        assert s.total == 35
        assert s.points[0].label == "Hot"
        assert s.points[0].value == 5

    def test_title(self):
        assert build_temperature_chart().title == "Lead Temperature"

    def test_colors(self):
        s = build_temperature_chart({"hot": 1})
        assert s.points[0].color == "#ef4444"


class TestIntentChart:
    def test_empty(self):
        s = build_intent_chart()
        assert s.total == 0

    def test_with_data(self):
        s = build_intent_chart({"price_interest": 15, "operator_requested": 5})
        assert s.total == 20

    def test_title(self):
        assert build_intent_chart().title == "Intent Breakdown"


class TestMissedSeverityChart:
    def test_empty(self):
        s = build_missed_severity_chart()
        assert s.total == 0
        assert len(s.points) == 4

    def test_with_data(self):
        s = build_missed_severity_chart({"critical": 3, "high": 7})
        assert s.total == 10

    def test_colors(self):
        s = build_missed_severity_chart({"critical": 1})
        assert s.points[0].color == "#dc2626"


class TestHandoffChart:
    def test_empty(self):
        s = build_handoff_chart()
        assert s.total == 0

    def test_with_data(self):
        s = build_handoff_chart({"open": 5, "resolved": 10})
        assert s.total == 15

    def test_title(self):
        assert build_handoff_chart().title == "Handoff Status"


class TestTopChart:
    def test_empty(self):
        s = build_top_chart([], "Test")
        assert s.total == 0

    def test_with_data(self):
        items = [("Qarshi", 20), ("Shahrisabz", 10)]
        s = build_top_chart(items, "Districts")
        assert s.total == 30
        assert s.points[0].label == "Qarshi"

    def test_limit_10(self):
        items = [(f"d{i}", i) for i in range(15)]
        s = build_top_chart(items, "Test")
        assert len(s.points) == MAX_TOP_ITEMS

    def test_sorted_desc(self):
        items = [("a", 5), ("b", 10), ("c", 1)]
        s = build_top_chart(items, "Test")
        assert s.points[0].value == 10


class TestBuildAllCharts:
    def test_empty(self):
        c = build_all_charts()
        assert isinstance(c, AnalyticsDashboardCharts)
        assert c.lead_temperature.total == 0

    def test_with_data(self):
        c = build_all_charts(
            temperature={"hot": 5},
            intents={"price_interest": 10},
        )
        assert c.lead_temperature.total == 5
        assert c.intent_breakdown.total == 10


class TestChartSeriesToDict:
    def test_empty(self):
        d = chart_series_to_dict(ChartSeries())
        assert d["total"] == 0
        assert d["points"] == []

    def test_with_points(self):
        s = ChartSeries(
            title="Test",
            points=[ChartPoint(label="A", value=5)],
            total=5,
        )
        d = chart_series_to_dict(s)
        assert d["title"] == "Test"
        assert len(d["points"]) == 1
        assert d["points"][0]["label"] == "A"

    def test_no_token(self):
        d = chart_series_to_dict(build_temperature_chart({"hot": 1}))
        import json

        txt = json.dumps(d)
        assert "sk-" not in txt
        assert "phone" not in txt.lower()


class TestMaxItems:
    def test_constant(self):
        assert MAX_TOP_ITEMS == 10
