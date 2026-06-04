"""Analytics page — the dead all-zero "Visual Charts" are replaced by real trends.

The old Temperature/Intent/Missed/Handoff charts were fed an all-zero API and
were fake. They are gone; the page now fetches the real /analytics/summary trend
endpoint. These tests pin the new section and the removal of the fake one.
"""

from __future__ import annotations

from pathlib import Path


def _t() -> str:
    return Path("apps/web/templates/analytics.html").read_text(encoding="utf-8")


class TestRealTrendsSection:
    def test_trend_heading(self):
        assert "Trendlar" in _t()

    def test_fetches_real_summary_endpoint(self):
        assert "/api/v1/admin/crm/analytics/summary" in _t()

    def test_trend_charts_present(self):
        c = _t()
        assert "tr-msg-chart" in c
        assert "tr-contact-chart" in c

    def test_real_totals_and_handoffs(self):
        c = _t()
        assert "Jami xabarlar" in c
        assert "tr-ho-open" in c and "tr-ho-resolved" in c

    def test_uzbek_labels(self):
        c = _t()
        assert "Kiruvchi" in c and "Chiquvchi" in c and "Yangi kontaktlar" in c

    def test_data_quality_note(self):
        assert "ishonchli yig'ilmaydi" in _t()


class TestOldFakeChartsRemoved:
    def test_no_fake_chart_titles(self):
        c = _t()
        for stale in (
            "Lead Temperature",
            "Intent Breakdown",
            "Missed Leads Severity",
            "Handoff Status",
        ):
            assert stale not in c

    def test_no_fake_chart_ids(self):
        c = _t()
        for stale in ("chartTemperature", "chartIntent", "chartMissed", "chartHandoff"):
            assert stale not in c

    def test_no_longer_calls_dead_charts_endpoint(self):
        # the all-zero /analytics/charts endpoint is no longer used by the page
        assert "/api/v1/admin/crm/analytics/charts" not in _t()


class TestStatesAndSafety:
    def test_loading_error_states(self):
        c = _t()
        assert "chartsLoading" in c and "chartsError" in c

    def test_same_origin_fetch_no_token(self):
        c = _t()
        assert 'credentials: "same-origin"' in c
        assert "sk-" not in c
        assert "session_id_hash" not in c


class TestQuickLinks:
    def test_links(self):
        c = _t()
        assert "/crm/missed-leads" in c
        assert "/crm/handoffs" in c


class TestSmoke:
    def test_api(self):
        from apps.api.main import app

        assert app is not None

    def test_web(self):
        from apps.web.main import app

        assert app is not None
