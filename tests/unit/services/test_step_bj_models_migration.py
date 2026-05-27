"""Tests for Step BJ — DB models, migration, schemas, settings."""
from __future__ import annotations

import importlib


class TestModels:
    def test_admin_session_model(self):
        from infrastructure.database.models.admin_session import AdminSessionModel
        assert AdminSessionModel.__tablename__ == "admin_sessions"

    def test_admin_login_attempt_model(self):
        from infrastructure.database.models.admin_session import AdminLoginAttemptModel
        assert AdminLoginAttemptModel.__tablename__ == "admin_login_attempts"

    def test_session_columns(self):
        from infrastructure.database.models.admin_session import AdminSessionModel
        cols = {c.name for c in AdminSessionModel.__table__.columns}
        assert "session_id_hash" in cols
        assert "admin_id" in cols
        assert "role" in cols
        assert "status" in cols
        assert "ip_address" in cols
        assert "user_agent" in cols
        assert "expires_at" in cols
        assert "revoked_at" in cols
        assert "metadata_json" in cols
        assert "last_seen_at" in cols

    def test_login_attempt_columns(self):
        from infrastructure.database.models.admin_session import AdminLoginAttemptModel
        cols = {c.name for c in AdminLoginAttemptModel.__table__.columns}
        assert "admin_id" in cols
        assert "ip_address" in cols
        assert "status" in cols
        assert "reason" in cols
        assert "metadata_json" in cols

    def test_session_unique_hash(self):
        from infrastructure.database.models.admin_session import AdminSessionModel
        col = AdminSessionModel.__table__.c.session_id_hash
        assert col.unique is True


class TestMigration:
    def test_importable(self):
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1630_e6f7g8h9i0j1_add_admin_sessions_login_attempts"
        )
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

    def test_revision(self):
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1630_e6f7g8h9i0j1_add_admin_sessions_login_attempts"
        )
        assert mod.revision == "e6f7g8h9i0j1"
        assert mod.down_revision == "d5e6f7g8h9i0"


class TestSchemas:
    def test_admin_login_request(self):
        from core.schemas.admin_auth import AdminLoginRequest
        r = AdminLoginRequest(admin_id="test1")
        assert r.admin_id == "test1"

    def test_admin_login_result(self):
        from core.schemas.admin_auth import AdminLoginResult
        r = AdminLoginResult(ok=True, session_id="abc")
        assert r.ok

    def test_admin_session_record(self):
        from core.schemas.admin_auth import AdminSessionRecord
        r = AdminSessionRecord(admin_id="u1", status="active")
        assert r.status == "active"

    def test_admin_session_principal(self):
        from core.schemas.admin_auth import AdminSessionPrincipal
        p = AdminSessionPrincipal(admin_id="u1", role="admin", is_authenticated=True)
        assert p.is_authenticated

    def test_admin_csrf_token(self):
        from core.schemas.admin_auth import AdminCSRFToken
        t = AdminCSRFToken(token="abc", is_valid=True)
        assert t.is_valid

    def test_admin_login_attempt_record(self):
        from core.schemas.admin_auth import AdminLoginAttemptRecord
        r = AdminLoginAttemptRecord(status="success")
        assert r.status == "success"

    def test_admin_logout_result(self):
        from core.schemas.admin_auth import AdminLogoutResult
        r = AdminLogoutResult(ok=True, session_revoked=True)
        assert r.session_revoked

    def test_login_request_frozen(self):
        import pytest

        from core.schemas.admin_auth import AdminLoginRequest
        obj = AdminLoginRequest()
        with pytest.raises(AttributeError):
            obj.admin_id = "x"  # type: ignore[misc]

    def test_login_result_frozen(self):
        import pytest

        from core.schemas.admin_auth import AdminLoginResult
        obj = AdminLoginResult()
        with pytest.raises(AttributeError):
            obj.ok = True  # type: ignore[misc]

    def test_session_record_frozen(self):
        import pytest

        from core.schemas.admin_auth import AdminSessionRecord
        obj = AdminSessionRecord()
        with pytest.raises(AttributeError):
            obj.status = "x"  # type: ignore[misc]

    def test_session_principal_frozen(self):
        import pytest

        from core.schemas.admin_auth import AdminSessionPrincipal
        obj = AdminSessionPrincipal()
        with pytest.raises(AttributeError):
            obj.admin_id = "x"  # type: ignore[misc]

    def test_logout_result_frozen(self):
        import pytest

        from core.schemas.admin_auth import AdminLogoutResult
        obj = AdminLogoutResult()
        with pytest.raises(AttributeError):
            obj.ok = True  # type: ignore[misc]


class TestSettings:
    def test_session_auth_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_auth_enabled"].default is False

    def test_cookie_name_default(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_cookie_name"].default == "vp_admin_session"

    def test_ttl_default_12(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_ttl_hours"].default == 12

    def test_secure_cookie_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_secure_cookie"].default is True

    def test_httponly_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_httponly"].default is True

    def test_samesite_default_lax(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_samesite"].default == "lax"

    def test_csrf_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_csrf_enabled"].default is False

    def test_max_attempts_default_5(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_login_max_attempts"].default == 5

    def test_window_default_15(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_login_window_minutes"].default == 15

    def test_block_default_15(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_login_block_minutes"].default == 15

    def test_audit_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_audit_enabled"].default is True
