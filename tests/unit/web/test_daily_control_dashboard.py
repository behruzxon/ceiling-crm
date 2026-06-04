"""Daily Control Dashboard (/dashboard) UI regression.

Renders the real template through the app's Jinja env (offline, no API/network)
and checks: Uzbek KPI labels, the client-side fetch targets the daily-summary
proxy path, KPI values are JS-filled placeholders (no fabricated numbers), the
old fake lead-analytics cards are gone, and null/error/empty/auth handling.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from apps.web.auth import require_dashboard_auth
from apps.web.main import app, templates

_KPI_LABELS = [
    "Bugungi xabarlar",
    "Kiruvchi xabarlar",
    "Chiquvchi javoblar",
    "Yangi kontaktlar",
    "Operator so'rovlari",
    "Javobsiz leadlar",
    "Noma'lum savollar",
    "Ochiq handofflar",
    "Hal qilingan handofflar",
]


def _render() -> str:
    return templates.get_template("dashboard.html").render(
        {"request": None, "active_page": "dashboard"}
    )


# ── template content ─────────────────────────────────────────────────────────


class TestTemplateRenders:
    def test_renders_without_error(self):
        assert "Kunlik Boshqaruv Paneli" in _render()

    @pytest.mark.parametrize("label", _KPI_LABELS)
    def test_uzbek_kpi_labels_present(self, label):
        assert label in _render()

    def test_range_toggle_labels(self):
        html = _render()
        for label in ("Bugun", "7 kun", "30 kun"):
            assert label in html

    def test_fetch_targets_daily_summary_proxy(self):
        html = _render()
        assert "/api/v1/admin/crm/daily-summary" in html
        assert 'credentials: "same-origin"' in html  # token stays server-side


class TestNoFakeStats:
    def test_kpi_values_are_js_placeholders(self):
        html = _render()
        # values are em-dash placeholders, filled by JS from the API — not numbers
        assert 'class="vp-kpi-value" id="kpi-total_messages">&mdash;' in html
        assert 'class="vp-kpi-value" id="kpi-open_handoffs">&mdash;' in html

    def test_old_fake_analytics_cards_removed(self):
        html = _render()
        for stale in ("Total Leads", "score_distribution", "data.total_leads", "fmt_number"):
            assert stale not in html


class TestNullErrorEmptyStates:
    def test_data_quality_note_for_unreliable_stats(self):
        html = _render()
        assert "hali ishonchli" in html  # null/unreliable communicated, not shown as 0
        assert "data_quality" in html  # JS branches on reliability flags

    def test_null_rendered_as_dash_not_zero(self):
        # fmt() maps null/undefined to an em-dash, never a fabricated 0
        assert 'return (n === null || n === undefined) ? "—"' in _render()

    def test_error_state_is_human_readable(self):
        html = _render()
        assert "Ma'lumotlarni yuklab bo'lmadi" in html
        assert ".catch(" in html  # fetch failure shows the banner, not raw JSON

    def test_empty_state_message(self):
        assert "Bugun hali aktivlik yo'q" in _render()


class TestSafetyAndLinks:
    def test_unknown_questions_rendered_with_textcontent(self):
        # API text injected via textContent (XSS-safe), never innerHTML
        assert "textContent" in _render()

    def test_links_to_handoffs_and_unknown_pages(self):
        html = _render()
        assert 'href="/crm/handoffs"' in html
        assert 'href="/agent/unknown-questions"' in html


# ── route + auth ─────────────────────────────────────────────────────────────


def _flatten_dependant_calls(dependant) -> list:
    calls = []
    for sub in getattr(dependant, "dependencies", []) or []:
        if getattr(sub, "call", None) is not None:
            calls.append(sub.call)
        calls.extend(_flatten_dependant_calls(sub))
    return calls


class TestDashboardRoute:
    def test_route_registered(self):
        scope = {"type": "http", "method": "GET", "path": "/dashboard"}
        matched = [
            r for r in app.routes if hasattr(r, "matches") and r.matches(scope)[0] == Match.FULL
        ]
        assert matched, "/dashboard route is missing"

    def test_route_behind_dashboard_auth(self):
        matched = [r for r in app.routes if getattr(r, "path", None) == "/dashboard"]
        assert matched
        calls = []
        for r in matched:
            calls.extend(_flatten_dependant_calls(r.dependant))
        assert require_dashboard_auth in calls

    def test_route_renders_200_when_authorised(self):
        app.dependency_overrides[require_dashboard_auth] = lambda: None
        try:
            resp = TestClient(app).get("/dashboard")
        finally:
            app.dependency_overrides.pop(require_dashboard_auth, None)
        assert resp.status_code == 200
        assert "Kunlik Boshqaruv Paneli" in resp.text
