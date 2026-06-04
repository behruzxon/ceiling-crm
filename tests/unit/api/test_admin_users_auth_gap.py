"""P1 security regression: the admin Users & Audit routers must require the API token.

``apps/api/routers/admin_users.py`` declares two routers — ``router``
(/api/v1/admin/users) and ``audit_router`` (/api/v1/admin/audit) — that were
the only admin API surface WITHOUT ``dependencies=[Depends(require_api_token)]``
while still being included in ``apps.api.main`` with no app-level auth, so their
endpoints were reachable with no token (privilege-escalation risk once DB RBAC
is wired). These tests pin the dependency at the source, on the router objects,
and on the registered route metadata, and exercise the fail-closed 401 path.

Offline: import / introspection + a direct call of the dependency — no DB,
Redis, Telegram, OpenAI, TestClient startup, or secrets.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import apps.api.dependencies.auth as auth_module
from apps.api.dependencies.auth import require_api_token

_SRC_FILE = "apps/api/routers/admin_users.py"

# (router attribute on the module, public prefix, a representative endpoint path)
_ROUTERS = [
    ("router", "/api/v1/admin/users", "/api/v1/admin/users"),
    ("audit_router", "/api/v1/admin/audit", "/api/v1/admin/audit/actions"),
]


def _get_router(attr: str):
    import importlib

    return getattr(importlib.import_module("apps.api.routers.admin_users"), attr)


def _router_dep_calls(router) -> list:
    """The callables behind a router's top-level dependencies."""
    out = []
    for dep in getattr(router, "dependencies", []) or []:
        call = getattr(dep, "dependency", None)
        if call is not None:
            out.append(call)
    return out


def _flatten_dependant_calls(dependant) -> list:
    """Recursively collect every dependency callable for a route's dependant."""
    calls = []
    for sub in getattr(dependant, "dependencies", []) or []:
        if getattr(sub, "call", None) is not None:
            calls.append(sub.call)
        calls.extend(_flatten_dependant_calls(sub))
    return calls


# ── (a) source uses require_api_token ────────────────────────────────────────


class TestSourceUsesAuth:
    def test_imports_require_api_token(self):
        assert "require_api_token" in Path(_SRC_FILE).read_text(encoding="utf-8")

    def test_router_declares_dependency(self):
        src = Path(_SRC_FILE).read_text(encoding="utf-8")
        # Both routers must carry the dependency — two declarations expected.
        assert src.count("dependencies=[Depends(require_api_token)]") >= 2


# ── (b) router objects carry the dependency ──────────────────────────────────


class TestRouterObjectHasDependency:
    @pytest.mark.parametrize("attr,prefix,_", _ROUTERS)
    def test_router_dependency_present(self, attr, prefix, _):
        router = _get_router(attr)
        assert require_api_token in _router_dep_calls(
            router
        ), f"admin_users.{attr}: router missing require_api_token dependency"

    @pytest.mark.parametrize("attr,prefix,_", _ROUTERS)
    def test_router_prefix_unchanged(self, attr, prefix, _):
        # The fix must not change the public prefix.
        assert _get_router(attr).prefix == prefix


# ── (c) registered route metadata enforces auth ──────────────────────────────


class TestAppRoutesEnforceAuth:
    @pytest.mark.parametrize("attr,prefix,sample_path", _ROUTERS)
    def test_sample_endpoint_has_auth_dependency(self, attr, prefix, sample_path):
        from apps.api.main import app

        matched = [r for r in app.routes if getattr(r, "path", None) == sample_path]
        assert matched, f"route not registered: {sample_path}"
        calls = []
        for r in matched:
            calls.extend(_flatten_dependant_calls(r.dependant))
        assert (
            require_api_token in calls
        ), f"{sample_path}: registered route is missing require_api_token"

    @pytest.mark.parametrize("prefix", ["/api/v1/admin/users", "/api/v1/admin/audit"])
    def test_every_route_under_prefix_has_auth(self, prefix):
        # Defense-in-depth: ALL endpoints under both prefixes are guarded.
        from apps.api.main import app

        routes = [r for r in app.routes if str(getattr(r, "path", "")).startswith(prefix)]
        assert routes, f"no routes registered under {prefix}"
        for r in routes:
            assert require_api_token in _flatten_dependant_calls(
                r.dependant
            ), f"{r.path}: missing require_api_token"


# ── (d) runtime fail-closed behavior (direct dependency call, fully offline) ──


def _settings_token_configured() -> SimpleNamespace:
    """Settings with an API token set — credentials are then mandatory."""
    return SimpleNamespace(
        api=SimpleNamespace(internal_token=SimpleNamespace(get_secret_value=lambda: "secret")),
        is_development=False,
    )


def _settings_prod_no_token() -> SimpleNamespace:
    """Production-like settings with no token configured — must fail closed."""
    return SimpleNamespace(
        api=SimpleNamespace(internal_token=None),
        is_development=False,
    )


class TestFailClosed:
    # NOTE: auth.py binds ``get_settings`` at module import (apps/api/dependencies/
    # auth.py:32), so require_api_token resolves the name in the auth module's
    # namespace — patching shared.config.get_settings would be a no-op. Patch the
    # module-bound reference so behavior is deterministic regardless of whether the
    # environment/.env has API_INTERNAL_TOKEN set (the reason this passed locally
    # but failed in token-less CI).
    async def test_tokenless_request_rejected_when_token_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auth_module, "get_settings", _settings_token_configured)
        with pytest.raises(HTTPException) as exc:
            await require_api_token(credentials=None)
        assert exc.value.status_code == 401

    async def test_production_without_token_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auth_module, "get_settings", _settings_prod_no_token)
        with pytest.raises(HTTPException) as exc:
            await require_api_token(credentials=None)
        assert exc.value.status_code == 401
