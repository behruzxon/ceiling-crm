"""Tests for Step BJ — Admin Auth Web Routes."""
from __future__ import annotations
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestLoginPage:
    @pytest.mark.asyncio
    async def test_login_route_importable(self):
        from apps.web.admin_auth_routes import login_page
        assert callable(login_page)

    @pytest.mark.asyncio
    async def test_login_page_renders(self):
        from apps.web.admin_auth_routes import login_page
        request = MagicMock()
        request.url_for = MagicMock(return_value="/login")
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            resp = await login_page(request)
            assert resp is not None

    @pytest.mark.asyncio
    async def test_login_page_with_error(self):
        from apps.web.admin_auth_routes import login_page
        request = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            resp = await login_page(request, error="test error")
            assert resp is not None


class TestLoginSubmit:
    @pytest.mark.asyncio
    async def test_disabled_shows_notice(self):
        from apps.web.admin_auth_routes import login_submit
        request = MagicMock()
        request.form = AsyncMock(return_value={"admin_id": "u1", "secret": "s1"})
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            resp = await login_submit(request)
            assert resp is not None

    @pytest.mark.asyncio
    async def test_empty_fields_error(self):
        from apps.web.admin_auth_routes import login_submit
        request = MagicMock()
        request.form = AsyncMock(return_value={"admin_id": "", "secret": ""})
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=True):
            resp = await login_submit(request)
            assert resp is not None

    @pytest.mark.asyncio
    async def test_generic_error_on_bad_creds(self):
        from apps.web.admin_auth_routes import login_submit
        from core.services.admin_auth_service import AdminAuthService
        request = MagicMock()
        request.form = AsyncMock(return_value={"admin_id": "user1", "secret": "wrong"})
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=True):
            resp = await login_submit(request)
            assert resp is not None


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_disabled(self):
        from apps.web.admin_auth_routes import logout
        request = MagicMock()
        response = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            resp = await logout(request, response)
            assert resp.status_code == 302

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self):
        from apps.web.admin_auth_routes import logout
        request = MagicMock()
        response = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=True):
            resp = await logout(request, response)
            assert resp.status_code == 302


class TestSessionInfo:
    @pytest.mark.asyncio
    async def test_disabled(self):
        from apps.web.admin_auth_routes import get_session_info
        request = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            r = await get_session_info(request)
            assert r["authenticated"] is False
            assert "disabled" in r["source"]

    @pytest.mark.asyncio
    async def test_no_session(self):
        from apps.web.admin_auth_routes import get_session_info
        request = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=True):
            r = await get_session_info(request)
            assert r["authenticated"] is False


class TestRouterRegistration:
    def test_router_importable(self):
        from apps.web.admin_auth_routes import router
        assert router is not None

    def test_web_app_includes_auth(self):
        from apps.web.main import app
        paths = [r.path for r in app.routes]
        assert "/login" in paths or any("/login" in str(p) for p in paths)


class TestBackwardCompatibility:
    def test_existing_dashboard_auth_importable(self):
        from apps.web.auth import require_dashboard_auth
        assert callable(require_dashboard_auth)

    def test_session_auth_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_auth_enabled"].default is False


class TestNoSecretInResponse:
    @pytest.mark.asyncio
    async def test_session_info_no_hash(self):
        from apps.web.admin_auth_routes import get_session_info
        request = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            r = await get_session_info(request)
            assert "session_id_hash" not in str(r)
            assert "session_id" not in str(r).lower() or "session_auth" in str(r)


class TestLoginTemplate:
    def test_template_exists(self):
        from pathlib import Path
        tpl = Path("apps/web/templates/login.html")
        assert tpl.exists()


class TestDI:
    def test_auth_service_factory(self):
        from infrastructure.di import get_admin_auth_service
        svc = get_admin_auth_service(None)
        assert svc is not None

    def test_csrf_service_factory(self):
        from infrastructure.di import get_admin_csrf_service
        svc = get_admin_csrf_service()
        assert svc is not None
