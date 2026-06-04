"""Route tests for GET /api/v1/admin/crm/daily-summary.

Offline: the DB dependency is overridden with a no-op fake and the service is
monkeypatched, so no real DB/Redis/network is touched. Auth presence is checked
by route introspection (mirrors the admin-auth regression tests).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from apps.api.dependencies.auth import require_api_token
from apps.api.main import app
from infrastructure.database.session import get_db

_PATH = "/api/v1/admin/crm/daily-summary"


async def _fake_db():
    yield object()  # never used: validation 400s first, or the service is mocked


def _flatten_dependant_calls(dependant) -> list:
    calls = []
    for sub in getattr(dependant, "dependencies", []) or []:
        if getattr(sub, "call", None) is not None:
            calls.append(sub.call)
        calls.extend(_flatten_dependant_calls(sub))
    return calls


# ── route registration + auth ────────────────────────────────────────────────


class TestRouteRegisteredWithAuth:
    def test_route_resolves(self):
        scope = {"type": "http", "method": "GET", "path": _PATH}
        matched = [
            r for r in app.routes if hasattr(r, "matches") and r.matches(scope)[0] == Match.FULL
        ]
        assert matched, f"{_PATH} is not registered"

    def test_requires_api_token(self):
        matched = [r for r in app.routes if getattr(r, "path", None) == _PATH]
        assert matched
        calls = []
        for r in matched:
            calls.extend(_flatten_dependant_calls(r.dependant))
        assert require_api_token in calls


# ── behavior (DB overridden, service mocked) ─────────────────────────────────


@pytest.fixture
def client():
    # Bypass auth + DB to test route LOGIC; auth presence is verified separately
    # (TestRouteRegisteredWithAuth) and fail-closed behavior by the #24 tests.
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[require_api_token] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_api_token, None)


class TestDailySummaryRoute:
    def test_invalid_range_rejected(self, client):
        resp = client.get(_PATH, params={"range": "bogus"})
        assert resp.status_code == 400
        assert "invalid range" in resp.json()["detail"]

    @pytest.mark.parametrize("rng", ["today", "7d", "30d"])
    def test_valid_ranges_accepted(self, client, monkeypatch, rng):
        async def _fake_summary(db, *, range_, source, timezone_name):
            return {"range": range_, "kpis": {}, "ok": True}

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_daily_summary.build_daily_summary", _fake_summary
        )
        resp = client.get(_PATH, params={"range": rng})
        assert resp.status_code == 200
        assert resp.json()["range"] == rng

    def test_default_range_is_today(self, client, monkeypatch):
        captured = {}

        async def _fake_summary(db, *, range_, source, timezone_name):
            captured["range"] = range_
            captured["source"] = source
            return {"range": range_}

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_daily_summary.build_daily_summary", _fake_summary
        )
        resp = client.get(_PATH)  # no range param
        assert resp.status_code == 200
        assert captured["range"] == "today"
        assert captured["source"] is None  # empty source → None (not applied)

    def test_response_shape_keys_present(self, client, monkeypatch):
        # Use the REAL service shaping with empty counts so the response proves no
        # fabricated stats (unreliable fields are null, flags false).
        from datetime import datetime

        from core.services.crm_daily_summary_service import Period, RawCounts, shape_summary

        _p = Period(start=datetime(2026, 6, 4), end=datetime(2026, 6, 4), timezone="Asia/Tashkent")

        async def _fake_summary(db, *, range_, source, timezone_name):
            return shape_summary(range_, _p, RawCounts())

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_daily_summary.build_daily_summary", _fake_summary
        )
        body = client.get(_PATH).json()
        assert set(body) >= {
            "range",
            "period",
            "kpis",
            "hourly_activity",
            "top_questions",
            "unknown_questions",
            "warnings",
            "data_quality",
        }
        assert body["kpis"]["price_requests"] is None
        assert body["kpis"]["hot_leads"] is None
        assert body["data_quality"]["source_reliable"] is False
        assert len(body["hourly_activity"]) == 24

    def test_empty_top_questions_is_empty_list(self, client, monkeypatch):
        # honest empty: no data → [], never a fabricated example list
        from datetime import datetime

        from core.services.crm_daily_summary_service import Period, RawCounts, shape_summary

        _p = Period(start=datetime(2026, 6, 4), end=datetime(2026, 6, 4), timezone="Asia/Tashkent")

        async def _fake_summary(db, *, range_, source, timezone_name):
            return shape_summary(range_, _p, RawCounts())

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_daily_summary.build_daily_summary", _fake_summary
        )
        body = client.get(_PATH).json()
        assert body["top_questions"] == []
        assert body["data_quality"]["top_questions_source"] == "agent_unknown_questions"

    def test_top_questions_real_list_passthrough(self, client, monkeypatch):
        from datetime import datetime

        from core.services.crm_daily_summary_service import Period, RawCounts, shape_summary

        _p = Period(start=datetime(2026, 6, 4), end=datetime(2026, 6, 4), timezone="Asia/Tashkent")
        grouped = [
            {
                "normalized": "narx qancha",
                "sample": "Narx qancha?",
                "count": 5,
                "last_seen": "2026-06-04T12:00:00+00:00",
                "reason": "price",
                "severity": "medium",
                "status": "new",
            }
        ]

        async def _fake_summary(db, *, range_, source, timezone_name):
            return shape_summary(range_, _p, RawCounts(top_questions=grouped))

        monkeypatch.setattr(
            "apps.api.routes.admin_crm_daily_summary.build_daily_summary", _fake_summary
        )
        body = client.get(_PATH).json()
        assert body["top_questions"] == grouped
        assert body["data_quality"]["top_questions_reliable"] is True
