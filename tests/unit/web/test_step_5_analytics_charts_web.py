"""Tests for Step 5 — Analytics Charts Web."""

from __future__ import annotations

from pathlib import Path


def _t() -> str:
    return Path("apps/web/templates/analytics.html").read_text(encoding="utf-8")


class TestChartsSection:
    def test_visual_charts_heading(self):
        assert "Visual Charts" in _t()

    def test_charts_grid(self):
        assert "chartsGrid" in _t()


class TestTemperatureChart:
    def test_container(self):
        assert "chartTemperature" in _t()

    def test_title(self):
        assert "Lead Temperature" in _t()

    def test_hot_bar(self):
        assert "Hot" in _t()

    def test_warm_bar(self):
        assert "Warm" in _t()

    def test_cold_bar(self):
        assert "Cold" in _t()


class TestIntentChart:
    def test_container(self):
        assert "chartIntent" in _t()

    def test_title(self):
        assert "Intent Breakdown" in _t()

    def test_price_bar(self):
        assert "Price" in _t()

    def test_operator_bar(self):
        assert "Operator" in _t()


class TestMissedChart:
    def test_container(self):
        assert "chartMissed" in _t()

    def test_title(self):
        assert "Missed Leads Severity" in _t()

    def test_critical_bar(self):
        assert "Critical" in _t()


class TestHandoffChart:
    def test_container(self):
        assert "chartHandoff" in _t()

    def test_title(self):
        assert "Handoff Status" in _t()

    def test_open_bar(self):
        c = _t()
        assert "Open" in c

    def test_resolved_bar(self):
        assert "Resolved" in _t()


class TestDesignSystem:
    def test_vp_card(self):
        assert "vp-card" in _t()

    def test_chart_bar_container(self):
        assert "chart-bar-container" in _t()

    def test_chart_bar_fill(self):
        assert "chart-bar-fill" in _t()


class TestQuickLinks:
    def test_missed_leads_link(self):
        assert "/crm/missed-leads" in _t()

    def test_handoff_link(self):
        assert "/crm/handoffs" in _t()


class TestMobile:
    def test_responsive(self):
        assert "analytics-2col-grid" in _t()


class TestJSFetch:
    def test_fetch_charts(self):
        assert "/api/v1/admin/crm/analytics/charts" in _t()

    def test_render_bars(self):
        assert "renderBars" in _t()


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _t()

    def test_no_session_hash(self):
        assert "session_id_hash" not in _t()

    def test_no_phone(self):
        c = _t().lower()
        assert "phone_number" not in c


class TestDocExists:
    def test_doc_119(self):
        assert Path("docs/AI_AGENT_SYSTEM/119_ANALYTICS_CHARTS.md").exists()


class TestSmoke:
    def test_api(self):
        from apps.api.main import app

        assert app is not None

    def test_web(self):
        from apps.web.main import app

        assert app is not None
