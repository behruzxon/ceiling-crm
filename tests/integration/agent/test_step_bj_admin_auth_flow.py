"""Integration tests for Step BJ — Admin Auth Flow."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock


class TestOldAuthStillWorks:
    def test_dashboard_auth_importable(self):
        from apps.web.auth import require_dashboard_auth
        assert callable(require_dashboard_auth)

    def test_api_app_importable(self):
        from apps.api.main import app
        assert app is not None

    def test_web_app_importable(self):
        from apps.web.main import app
        assert app is not None


class TestSessionAuthDisabledFlow:
    def test_session_auth_default_off(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_auth_enabled"].default is False

    @pytest.mark.asyncio
    async def test_login_disabled_notice(self):
        from apps.web.admin_auth_routes import login_page
        request = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            resp = await login_page(request)
            assert resp is not None

    @pytest.mark.asyncio
    async def test_me_session_disabled(self):
        from apps.web.admin_auth_routes import get_session_info
        request = MagicMock()
        with patch("apps.web.admin_auth_routes._get_session_auth_enabled", return_value=False):
            r = await get_session_info(request)
            assert not r["authenticated"]


class TestSessionCreateValidateFlow:
    def test_create_and_validate(self):
        from core.services.admin_auth_service import AdminAuthService
        svc = AdminAuthService()
        cr = svc.create_session("admin1", "admin")
        assert cr.ok
        d = svc.build_session_dict(cr)
        vr = svc.validate_session(d)
        assert vr.ok
        assert vr.admin_id == "admin1"

    def test_create_revoke_invalid(self):
        from core.services.admin_auth_service import AdminAuthService
        svc = AdminAuthService()
        cr = svc.create_session("admin1", "admin")
        d = svc.build_session_dict(cr)
        d.update(svc.build_revoke_dict("admin1"))
        vr = svc.validate_session(d)
        assert not vr.ok
        assert "revoked" in vr.error

    def test_create_rotate_old_replaced(self):
        from core.services.admin_auth_service import AdminAuthService
        svc = AdminAuthService()
        old = svc.create_session("admin1")
        old_dict = svc.build_session_dict(old)
        old_dict.update(svc.build_replace_dict())
        vr = svc.validate_session(old_dict)
        assert not vr.ok
        assert "replaced" in vr.error
        new = svc.create_session("admin1")
        new_dict = svc.build_session_dict(new)
        vr2 = svc.validate_session(new_dict)
        assert vr2.ok


class TestLoginAttemptTracking:
    def test_track_and_block(self):
        from core.services.admin_auth_service import AdminAuthService
        svc = AdminAuthService()
        for i in range(4):
            d = svc.record_login_attempt("admin1", status="failed")
            assert d["status"] == "failed"
        r = svc.is_login_blocked(4, max_attempts=5)
        assert not r.blocked
        r = svc.is_login_blocked(5, max_attempts=5)
        assert r.blocked


class TestCSRFFlow:
    def test_generate_and_validate(self):
        from core.services.admin_csrf_service import AdminCSRFService
        svc = AdminCSRFService()
        token = svc.generate_csrf_token("session_hash", "secret_key")
        r = svc.validate_csrf_token(token, "session_hash", "secret_key", enabled=True)
        assert r.ok

    def test_disabled_skips(self):
        from core.services.admin_csrf_service import AdminCSRFService
        svc = AdminCSRFService()
        r = svc.validate_csrf_token("garbage", "", "", enabled=False)
        assert r.ok


class TestDBRBACWithSession:
    def test_session_principal_resolve(self):
        from core.services.admin_rbac_service import AdminRBACService
        db_user = {"role": "operator", "is_active": True}
        role, src = AdminRBACService.resolve_role_with_db(
            "admin1", db_user, db_rbac_enabled=True,
        )
        assert role == "operator"
        assert src == "db"


class TestNoTokenLeak:
    def test_auth_error_sanitized(self):
        from core.services.admin_auth_service import AdminAuthService
        err = AdminAuthService.sanitize_auth_error("sk-secret123 invalid")
        assert "sk-" not in err

    def test_session_response_no_hash(self):
        from core.services.admin_auth_service import AdminAuthService
        d = AdminAuthService.sanitize_session_for_response({
            "session_id_hash": "abc",
            "admin_id": "u1",
        })
        assert "session_id_hash" not in d

    def test_csrf_error_sanitized(self):
        from core.services.admin_csrf_service import AdminCSRFService
        err = AdminCSRFService.sanitize_csrf_error("sk-secret in csrf")
        assert "sk-" not in err


class TestNoSendOccurs:
    def test_no_telegram_import_in_auth(self):
        import inspect
        import core.services.admin_auth_service as mod
        source = inspect.getsource(mod)
        assert "aiogram" not in source
        assert "send_message" not in source

    def test_no_telegram_import_in_csrf(self):
        import inspect
        import core.services.admin_csrf_service as mod
        source = inspect.getsource(mod)
        assert "aiogram" not in source


class TestAuditIntegration:
    def test_login_attempt_audit_entry(self):
        from core.services.admin_audit_log_service import AdminAuditLogService
        from core.services.admin_auth_service import AdminAuthService
        attempt = AdminAuthService.record_login_attempt("u1", "127.0.0.1", "success")
        audit = AdminAuditLogService.build_entry(
            actor_admin_id=attempt["admin_id"],
            action="admin_user.login",
            status="success",
        )
        assert audit["action"] == "admin_user.login"
        assert audit["actor_admin_id"] == "u1"


class TestSmoke:
    def test_scheduler_imports(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
