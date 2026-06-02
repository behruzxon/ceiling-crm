"""P0 security regression: every admin/security router must require the API token.

Four admin routers previously declared their APIRouter WITHOUT
``dependencies=[Depends(require_api_token)]`` and the FastAPI app has no app-level
auth dependency, so their endpoints (campaign drafts, contact merge, security
dashboard, session-revoke / admin-disable) were reachable with no token. These
tests pin that the token dependency is present at the source, on the router
object, and on the registered route metadata.

Offline: import / introspection only — no DB, Redis, Telegram, OpenAI, or secrets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.dependencies.auth import require_api_token

# (module path, router prefix, a representative endpoint path on that router)
_ROUTERS = [
    (
        "apps.api.routes.admin_crm_campaigns",
        "/api/v1/admin/crm/campaigns",
        "/api/v1/admin/crm/campaigns/segments",
    ),
    (
        "apps.api.routes.admin_crm_merge",
        "/api/v1/admin/crm",
        "/api/v1/admin/crm/contacts/merge/preview",
    ),
    (
        "apps.api.routes.admin_security",
        "/api/v1/admin/security",
        "/api/v1/admin/security/dashboard",
    ),
    (
        "apps.api.routes.admin_security_actions",
        "/api/v1/admin/security",
        "/api/v1/admin/security/sessions/{session_id}/revoke",
    ),
]

_SRC_FILES = [
    "apps/api/routes/admin_crm_campaigns.py",
    "apps/api/routes/admin_crm_merge.py",
    "apps/api/routes/admin_security.py",
    "apps/api/routes/admin_security_actions.py",
]


def _import_router(module_path: str):
    import importlib

    return importlib.import_module(module_path).router


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
    @pytest.mark.parametrize("path", _SRC_FILES)
    def test_imports_require_api_token(self, path):
        assert "require_api_token" in Path(path).read_text(encoding="utf-8")

    @pytest.mark.parametrize("path", _SRC_FILES)
    def test_router_declares_dependency(self, path):
        src = Path(path).read_text(encoding="utf-8")
        assert "dependencies=[Depends(require_api_token)]" in src


# ── (b) router object carries the dependency ─────────────────────────────────


class TestRouterObjectHasDependency:
    @pytest.mark.parametrize("module_path,prefix,_", _ROUTERS)
    def test_router_dependency_present(self, module_path, prefix, _):
        router = _import_router(module_path)
        assert require_api_token in _router_dep_calls(
            router
        ), f"{module_path}: router missing require_api_token dependency"

    @pytest.mark.parametrize("module_path,prefix,_", _ROUTERS)
    def test_router_prefix_unchanged(self, module_path, prefix, _):
        # The fix must not change the public prefix.
        assert _import_router(module_path).prefix == prefix


# ── (c) registered route metadata enforces auth ──────────────────────────────


class TestAppRoutesEnforceAuth:
    @pytest.mark.parametrize("module_path,prefix,sample_path", _ROUTERS)
    def test_sample_endpoint_has_auth_dependency(self, module_path, prefix, sample_path):
        from apps.api.main import app

        matched = [r for r in app.routes if getattr(r, "path", None) == sample_path]
        assert matched, f"route not registered: {sample_path}"
        calls = []
        for r in matched:
            calls.extend(_flatten_dependant_calls(r.dependant))
        assert (
            require_api_token in calls
        ), f"{sample_path}: registered route is missing require_api_token"

    def test_every_campaigns_route_has_auth(self):
        # Defense-in-depth: ALL endpoints under the campaigns prefix are guarded.
        from apps.api.main import app

        prefix = "/api/v1/admin/crm/campaigns"
        routes = [r for r in app.routes if str(getattr(r, "path", "")).startswith(prefix)]
        assert routes
        for r in routes:
            assert require_api_token in _flatten_dependant_calls(
                r.dependant
            ), f"{r.path}: missing require_api_token"

    def test_security_actions_routes_have_auth(self):
        from apps.api.main import app

        # security-actions endpoints are the most dangerous (revoke/disable).
        routes = [
            r
            for r in app.routes
            if str(getattr(r, "path", "")).startswith("/api/v1/admin/security/")
        ]
        assert routes
        for r in routes:
            assert require_api_token in _flatten_dependant_calls(
                r.dependant
            ), f"{r.path}: missing require_api_token"


# ── smoke ─────────────────────────────────────────────────────────────────


class TestSmoke:
    def test_app_imports(self):
        from apps.api.main import app

        assert app is not None and len(app.routes) > 0
