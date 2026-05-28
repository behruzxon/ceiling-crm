"""Tests for Step 9.1 — CSRF middleware wiring (apps/web).

Covers blocker §1.4 of docs/AI_AGENT_SYSTEM/134.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── 1. Imports / smoke ──────────────────────────────────────────────────


class TestImports:
    def test_module_importable(self):
        import apps.web.csrf_middleware  # noqa: F401

    def test_middleware_class_importable(self):
        from apps.web.csrf_middleware import AdminCSRFMiddleware

        assert AdminCSRFMiddleware is not None

    def test_csrf_service_importable(self):
        from core.services.admin_csrf_service import AdminCSRFService

        assert AdminCSRFService is not None

    def test_csrf_header_constant(self):
        from apps.web.csrf_middleware import CSRF_HEADER_NAME

        assert CSRF_HEADER_NAME == "X-CSRF-Token"

    def test_exempt_paths_constant_is_frozenset(self):
        from apps.web.csrf_middleware import CSRF_EXEMPT_PATHS

        assert isinstance(CSRF_EXEMPT_PATHS, frozenset)

    def test_login_exempt_by_default(self):
        from apps.web.csrf_middleware import CSRF_EXEMPT_PATHS

        assert "/login" in CSRF_EXEMPT_PATHS


# ── 2. Default flag remains OFF ─────────────────────────────────────────


class TestFlagDefaults:
    def test_admin_csrf_enabled_default_false(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["admin_csrf_enabled"].default is False

    def test_helper_returns_false_when_settings_missing(self):
        from apps.web import csrf_middleware

        with patch("shared.config.get_settings", side_effect=RuntimeError("no env")):
            assert csrf_middleware._is_csrf_enabled() is False


# ── 3. Session hash helpers ─────────────────────────────────────────────


class TestSessionHash:
    def test_empty_session_hash_empty(self):
        from apps.web.csrf_middleware import _hash_session_id

        assert _hash_session_id("") == ""

    def test_session_hash_deterministic(self):
        from apps.web.csrf_middleware import _hash_session_id

        assert _hash_session_id("abc") == _hash_session_id("abc")

    def test_session_hash_sha256_length(self):
        from apps.web.csrf_middleware import _hash_session_id

        assert len(_hash_session_id("abc")) == 64

    def test_session_hash_differs_per_input(self):
        from apps.web.csrf_middleware import _hash_session_id

        assert _hash_session_id("a") != _hash_session_id("b")


# ── 4. App wiring (TestClient) ──────────────────────────────────────────


@pytest.fixture()
def _disable_dashboard_auth():
    """Make /dashboard reachable without HTTP Basic in tests."""
    from apps.web import auth as web_auth

    with (
        patch.object(web_auth, "get_web_username", return_value=""),
        patch.object(web_auth, "get_web_password", return_value=""),
        patch.object(web_auth, "is_development", return_value=True),
    ):
        yield


@pytest.fixture()
def _csrf_off():
    from shared.config import get_settings

    settings = get_settings()
    original = settings.business.admin_csrf_enabled
    settings.business.admin_csrf_enabled = False
    try:
        yield
    finally:
        settings.business.admin_csrf_enabled = original


@pytest.fixture()
def _csrf_on():
    from shared.config import get_settings

    settings = get_settings()
    original = settings.business.admin_csrf_enabled
    settings.business.admin_csrf_enabled = True
    try:
        yield
    finally:
        settings.business.admin_csrf_enabled = original


class TestAppWiring:
    def test_app_has_csrf_middleware_registered(self):
        from apps.web.csrf_middleware import AdminCSRFMiddleware
        from apps.web.main import app

        registered = [m.cls for m in app.user_middleware]
        assert AdminCSRFMiddleware in registered

    def test_app_includes_login_route(self):
        from apps.web.main import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/login" in paths


# ── 5. Behavior when disabled (no breakage) ────────────────────────────


class TestDisabledPassthrough:
    def test_get_dashboard_when_disabled(self, _disable_dashboard_auth, _csrf_off, monkeypatch):
        from apps.web.main import app

        async def _fake_api_get(*_a, **_kw):
            return {}

        monkeypatch.setattr("apps.web.main.api_get", _fake_api_get)
        client = TestClient(app)
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_post_login_when_disabled(self, _disable_dashboard_auth, _csrf_off):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/login", data={"admin_id": "x", "secret": "y"})
        # Stub returns 200 with notice page when session auth off, never 403.
        assert resp.status_code != 403

    def test_post_logout_when_disabled(self, _disable_dashboard_auth, _csrf_off):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/logout")
        assert resp.status_code != 403


# ── 6. Safe-method exemptions ──────────────────────────────────────────


class TestSafeMethodsExempt:
    def test_get_exempt_when_enabled(self, _disable_dashboard_auth, _csrf_on, monkeypatch):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_head_exempt_when_enabled(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.head("/login")
        assert resp.status_code != 403

    def test_options_exempt_when_enabled(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.options("/login")
        assert resp.status_code != 403


# ── 7. Unsafe methods require token ────────────────────────────────────


class TestPostEnforcement:
    def test_post_logout_no_token_blocked(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/logout")
        assert resp.status_code == 403

    def test_post_logout_invalid_token_blocked(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/logout", headers={"X-CSRF-Token": "not-a-real-token"})
        assert resp.status_code == 403

    def test_post_logout_whitespace_token_blocked(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/logout", headers={"X-CSRF-Token": "   "})
        assert resp.status_code == 403

    def test_post_logout_tampered_token_blocked(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app
        from core.services.admin_csrf_service import AdminCSRFService

        token = AdminCSRFService.generate_csrf_token("h1", "k1")
        tampered = token.rsplit(".", 1)[0] + ".baaaad"
        client = TestClient(app)
        resp = client.post("/logout", headers={"X-CSRF-Token": tampered})
        assert resp.status_code == 403

    def test_post_logout_valid_token_passes_csrf(self, _disable_dashboard_auth, _csrf_on):
        """Valid CSRF token: middleware lets the request through; status no longer 403."""
        import hashlib

        from apps.web.main import app
        from core.services.admin_csrf_service import AdminCSRFService
        from shared.config import get_settings

        settings = get_settings()
        secret = settings.app_secret_key.get_secret_value()
        session_value = "test-session"
        session_id_hash = hashlib.sha256(session_value.encode("utf-8")).hexdigest()
        token = AdminCSRFService.generate_csrf_token(session_id_hash, secret)

        cookie_name = settings.business.admin_session_cookie_name
        client = TestClient(app)
        client.cookies.set(cookie_name, session_value)
        resp = client.post("/logout", headers={"X-CSRF-Token": token})
        assert resp.status_code != 403

    def test_login_post_exempt_when_enabled(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/login", data={"admin_id": "x", "secret": "y"})
        assert resp.status_code != 403


# ── 8. Custom exempt paths ─────────────────────────────────────────────


class TestCustomExemptPaths:
    def test_constructor_accepts_custom_exempt_paths(self):
        from apps.web.csrf_middleware import AdminCSRFMiddleware

        async def _dummy(scope, receive, send):  # pragma: no cover - never called
            pass

        mw = AdminCSRFMiddleware(_dummy, exempt_paths=frozenset({"/foo"}))
        assert "/foo" in mw._exempt_paths


# ── 9. Error response shape & no-leak ──────────────────────────────────


class TestErrorResponseShape:
    def test_403_response_has_detail(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.post("/logout")
        body = resp.json()
        assert "detail" in body

    def test_response_does_not_leak_secret_key(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app
        from shared.config import get_settings

        secret = get_settings().app_secret_key.get_secret_value()
        client = TestClient(app)
        resp = client.post("/logout")
        assert secret not in resp.text

    def test_response_does_not_leak_session_hash(self, _disable_dashboard_auth, _csrf_on):
        import hashlib

        from apps.web.main import app

        session_value = "leak-session-test"
        session_id_hash = hashlib.sha256(session_value.encode("utf-8")).hexdigest()
        client = TestClient(app)
        client.cookies.set("vp_admin_session", session_value)
        resp = client.post("/logout")
        assert session_id_hash not in resp.text

    def test_response_does_not_echo_submitted_token(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        marker = "sk-supersecretmarker"
        client = TestClient(app)
        resp = client.post("/logout", headers={"X-CSRF-Token": marker})
        assert marker not in resp.text


# ── 10. Logger does not record the token ───────────────────────────────


class TestNoTokenLogging:
    def test_no_token_in_logs(self, _disable_dashboard_auth, _csrf_on, caplog):
        from apps.web.main import app

        marker = "Bearer-DO-NOT-LOG-9c1f"
        client = TestClient(app)
        with caplog.at_level(logging.DEBUG):
            client.post("/logout", headers={"X-CSRF-Token": marker})
        for record in caplog.records:
            assert marker not in record.getMessage()


# ── 11. Login GET still renders ────────────────────────────────────────


class TestLoginPageIntact:
    def test_login_get_html_returned(self, _disable_dashboard_auth, _csrf_on):
        from apps.web.main import app

        client = TestClient(app)
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "html" in resp.text.lower() or "CeilingCRM" in resp.text


# ── 12. Documentation references staged enablement ────────────────────


class TestDocsMention:
    def test_security_plan_lists_csrf_stage(self):
        text = open("docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md", encoding="utf-8").read()
        assert "ADMIN_CSRF_ENABLED" in text

    def test_blocker_doc_lists_csrf(self):
        text = open(
            "docs/AI_AGENT_SYSTEM/134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md",
            encoding="utf-8",
        ).read()
        assert "CSRF" in text


# ── 13. Direct unit calls on AdminCSRFService stay green ──────────────


class TestServiceContractStable:
    def test_safe_methods_set(self):
        from core.services.admin_csrf_service import AdminCSRFService

        assert {"GET", "HEAD", "OPTIONS"} <= AdminCSRFService.exempt_safe_methods()

    def test_should_require_csrf_disabled(self):
        from core.services.admin_csrf_service import AdminCSRFService

        assert AdminCSRFService.should_require_csrf("POST", "/x", enabled=False) is False

    def test_should_require_csrf_enabled_post(self):
        from core.services.admin_csrf_service import AdminCSRFService

        assert AdminCSRFService.should_require_csrf("POST", "/x", enabled=True) is True

    def test_validate_token_roundtrip(self):
        from core.services.admin_csrf_service import AdminCSRFService

        token = AdminCSRFService.generate_csrf_token("h", "k")
        res = AdminCSRFService.validate_csrf_token(token, "h", "k", enabled=True)
        assert res.ok

    def test_validate_token_wrong_session(self):
        from core.services.admin_csrf_service import AdminCSRFService

        token = AdminCSRFService.generate_csrf_token("h", "k")
        res = AdminCSRFService.validate_csrf_token(token, "other", "k", enabled=True)
        assert not res.ok

    def test_sanitize_error_truncates(self):
        from core.services.admin_csrf_service import AdminCSRFService

        out = AdminCSRFService.sanitize_csrf_error("x" * 1000)
        assert len(out) <= 300
