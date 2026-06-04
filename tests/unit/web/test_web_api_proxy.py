"""Regression: the web app must proxy browser /api/v1/admin/* calls to the API.

Templates issue client-side ``fetch('/api/v1/admin/...')`` against the WEB
origin (:8001), but the admin API routes live on a separate service (:8000).
Without a web-side proxy every CRM/Agent mutation and lazy-loaded panel 404s.
This pins that:
  - the catch-all proxy route is registered for every browser HTTP method,
  - it forwards method/path/query/body server-side (token stays off the browser),
  - it stays behind the dashboard auth dependency (still 401 without creds in prod),
  - it adds no capability of its own (the API keeps enforcing feature flags).

Offline: route introspection + TestClient with the forwarder mocked — no real
API/DB/Redis/network/Telegram/OpenAI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

import apps.web.auth as web_auth
import apps.web.main as web_main
from apps.web.main import app

# Representative browser calls taken verbatim from the templates' fetch() targets.
_BROWSER_CALLS = [
    ("POST", "/api/v1/admin/crm/handoffs/1/take"),
    ("POST", "/api/v1/admin/crm/conversations/1/operator-reply"),
    ("PATCH", "/api/v1/admin/agent/knowledge/5"),
    ("POST", "/api/v1/admin/agent/unknown-questions/3/promote-to-faq"),
    ("GET", "/api/v1/admin/crm/operator-digest/daily"),
    ("GET", "/api/v1/admin/crm/inbox/live-summary"),
]


def _resolve(method: str, path: str) -> str | None:
    scope = {"type": "http", "method": method, "path": path}
    for route in app.routes:
        if not hasattr(route, "matches"):
            continue
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return getattr(route, "name", None)
    return None


class _Recorder:
    """Stand-in for proxy_api_request that records the forwarded request."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(
        self, method, path, *, query_string="", body=None, content_type=None
    ) -> tuple[int, bytes, str]:
        self.calls.append({"method": method, "path": path, "query": query_string, "body": body})
        return 200, b'{"ok": true}', "application/json"


# ── (a) the proxy route is registered, so admin API paths don't 404 ──────────


class TestProxyRouteRegistered:
    @pytest.mark.parametrize("method,path", _BROWSER_CALLS)
    def test_admin_api_path_resolves_to_proxy(self, method, path):
        assert (
            _resolve(method, path) == "proxy_admin_api"
        ), f"{method} {path} is not served by the web app — would 404"

    def test_proxy_covers_all_browser_methods(self):
        for m in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            assert _resolve(m, "/api/v1/admin/crm/handoffs/1/take") == "proxy_admin_api"


# ── (b) the proxy forwards method/path/query/body server-side ────────────────


class TestProxyForwards:
    def test_post_forwards_and_does_not_404(self, monkeypatch):
        rec = _Recorder()
        monkeypatch.setattr(web_main, "proxy_api_request", rec)
        resp = TestClient(app).post("/api/v1/admin/crm/handoffs/9/take", json={"x": 1})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert rec.calls[0]["method"] == "POST"
        assert rec.calls[0]["path"] == "/api/v1/admin/crm/handoffs/9/take"

    def test_get_forwards_query_string(self, monkeypatch):
        rec = _Recorder()
        monkeypatch.setattr(web_main, "proxy_api_request", rec)
        resp = TestClient(app).get("/api/v1/admin/crm/operator-digest/daily?hours=24")
        assert resp.status_code == 200
        assert rec.calls[0]["query"] == "hours=24"

    def test_dot_segment_rejected_without_forwarding(self, monkeypatch):
        # Defense-in-depth: a ".." segment must not be forwarded (httpx would
        # normalize it out of the /api/v1/admin/ prefix into a sibling endpoint).
        # Called at the handler level because the HTTP client normalises "../"
        # before it would ever reach the route.
        import asyncio

        rec = _Recorder()
        monkeypatch.setattr(web_main, "proxy_api_request", rec)
        resp = asyncio.run(web_main.proxy_admin_api(path="../leads", request=None))
        assert resp.status_code == 400
        assert rec.calls == []  # never forwarded


# ── (c) the proxy stays behind dashboard auth (fail-closed in production) ─────


class TestProxyBehindAuth:
    @staticmethod
    def _configure_prod_auth(monkeypatch):
        monkeypatch.setattr(web_auth, "get_web_username", lambda: "admin")
        monkeypatch.setattr(web_auth, "get_web_password", lambda: "secret")
        monkeypatch.setattr(web_auth, "is_development", lambda: False)

    def test_unauthenticated_request_blocked_before_forwarding(self, monkeypatch):
        self._configure_prod_auth(monkeypatch)
        reached = {"n": 0}

        async def _should_not_run(*a, **k):
            reached["n"] += 1
            return 200, b"{}", "application/json"

        monkeypatch.setattr(web_main, "proxy_api_request", _should_not_run)
        resp = TestClient(app).post("/api/v1/admin/crm/handoffs/1/take")
        assert resp.status_code == 401
        assert reached["n"] == 0  # auth blocked it before any forwarding

    def test_authenticated_request_forwarded(self, monkeypatch):
        self._configure_prod_auth(monkeypatch)
        rec = _Recorder()
        monkeypatch.setattr(web_main, "proxy_api_request", rec)
        resp = TestClient(app).post("/api/v1/admin/crm/handoffs/1/take", auth=("admin", "secret"))
        assert resp.status_code == 200
        assert rec.calls[0]["method"] == "POST"
