"""Route tests for the real analytics-summary and missed-leads endpoints.

Offline: DB + auth dependencies overridden; the loader is monkeypatched so the
REAL build_summary aggregation runs (proving no fake data). No DB/network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from apps.api.dependencies.auth import require_api_token
from apps.api.main import app
from core.schemas.crm_missed_leads import MissedLeadItem
from infrastructure.database.session import get_db

_ANALYTICS = "/api/v1/admin/crm/analytics/summary"
_MISSED = "/api/v1/admin/crm/missed-leads"


async def _fake_db():
    yield object()


def _flatten(dep):
    calls = []
    for sub in getattr(dep, "dependencies", []) or []:
        if getattr(sub, "call", None) is not None:
            calls.append(sub.call)
        calls.extend(_flatten(sub))
    return calls


def _resolves(method, path):
    scope = {"type": "http", "method": method, "path": path}
    return any(r.matches(scope)[0] == Match.FULL for r in app.routes if hasattr(r, "matches"))


def _auth_on(path):
    for r in app.routes:
        if getattr(r, "path", None) == path:
            if require_api_token in _flatten(r.dependant):
                return True
    return False


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[require_api_token] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_api_token, None)


# ── analytics summary ────────────────────────────────────────────────────────


class TestAnalyticsSummaryRoute:
    def test_registered_and_auth(self):
        assert _resolves("GET", _ANALYTICS)
        assert _auth_on(_ANALYTICS)

    def test_invalid_range_400(self, client):
        assert client.get(_ANALYTICS, params={"range": "bogus"}).status_code == 400

    def test_valid_range_shape(self, client, monkeypatch):
        async def _fake(db, *, range_, timezone_name):
            return {"range": range_, "trend": [], "totals": {}, "data_quality": {}}

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_analytics_summary.build_analytics_summary", _fake
        )
        r = client.get(_ANALYTICS, params={"range": "7d"})
        assert r.status_code == 200
        assert set(r.json()) >= {"range", "trend", "totals", "data_quality"}


# ── missed-leads (real, via existing build_summary) ──────────────────────────


def _items():
    return [
        MissedLeadItem(contact_id=1, severity="critical", reason="unanswered", minutes_waiting=200),
        MissedLeadItem(contact_id=2, severity="medium", reason="unanswered", minutes_waiting=20),
    ]


class TestMissedLeadsRoute:
    def test_registered_and_auth(self):
        assert _resolves("GET", _MISSED)
        assert _resolves("GET", _MISSED + "/summary")
        assert _auth_on(_MISSED + "/summary")

    def test_invalid_range_400(self, client):
        assert client.get(_MISSED + "/summary", params={"range": "bad"}).status_code == 400

    def test_summary_uses_real_aggregation(self, client, monkeypatch):
        async def _fake_collect(db, period, limit=100):
            return _items()

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_missed_leads.collect_missed_items", _fake_collect
        )
        body = client.get(_MISSED + "/summary", params={"range": "7d"}).json()
        assert body["total"] == 2
        assert body["critical"] == 1
        assert body["medium"] == 1
        assert body["oldest_wait_minutes"] == 200
        # reason-categories stay 0 (honest) and data_quality flags them
        assert body["hot_unanswered"] == 0
        assert body["data_quality"]["reason_categories_reliable"] is False

    def test_list_severity_filter(self, client, monkeypatch):
        async def _fake_collect(db, period, limit=100):
            return _items()

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_missed_leads.collect_missed_items", _fake_collect
        )
        body = client.get(_MISSED, params={"range": "7d", "severity": "critical"}).json()
        assert body["count"] == 1
        assert body["items"][0]["contact_id"] == 1
        assert body["items"][0]["severity"] == "critical"

    def test_no_fake_when_empty(self, client, monkeypatch):
        async def _fake_collect(db, period, limit=100):
            return []

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_missed_leads.collect_missed_items", _fake_collect
        )
        body = client.get(_MISSED + "/summary", params={"range": "today"}).json()
        assert body["total"] == 0 and body["critical"] == 0
        assert client.get(_MISSED, params={"range": "today"}).json() == {
            "items": [],
            "count": 0,
            "data_quality": {"reason_categories_reliable": False, "severity_basis": "wait_time"},
        }
