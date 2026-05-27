"""Tests for Step BJ — AdminAuthService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.services.admin_auth_service import AdminAuthService, CookieSettings

svc = AdminAuthService


class TestGenerateSessionId:
    def test_not_empty(self):
        sid = svc.generate_session_id()
        assert len(sid) > 30

    def test_unique(self):
        s1 = svc.generate_session_id()
        s2 = svc.generate_session_id()
        assert s1 != s2

    def test_url_safe(self):
        sid = svc.generate_session_id()
        assert " " not in sid
        assert "+" not in sid


class TestHashSessionId:
    def test_deterministic(self):
        h1 = svc.hash_session_id("test123")
        h2 = svc.hash_session_id("test123")
        assert h1 == h2

    def test_different_input(self):
        h1 = svc.hash_session_id("abc")
        h2 = svc.hash_session_id("def")
        assert h1 != h2

    def test_sha256_length(self):
        h = svc.hash_session_id("test")
        assert len(h) == 64

    def test_raw_not_in_hash(self):
        sid = "mysecrettoken123"
        h = svc.hash_session_id(sid)
        assert sid not in h


class TestCreateSession:
    def test_success(self):
        r = svc.create_session("admin1", "admin")
        assert r.ok
        assert r.admin_id == "admin1"
        assert r.role == "admin"
        assert r.session_id != ""
        assert r.session_id_hash != ""

    def test_hash_matches(self):
        r = svc.create_session("admin1")
        assert r.session_id_hash == svc.hash_session_id(r.session_id)

    def test_raw_not_stored_in_hash(self):
        r = svc.create_session("admin1")
        assert r.session_id not in r.session_id_hash

    def test_empty_admin_id(self):
        r = svc.create_session("")
        assert not r.ok
        assert "admin_id" in r.error

    def test_whitespace_admin_id(self):
        r = svc.create_session("   ")
        assert not r.ok

    def test_trims_admin_id(self):
        r = svc.create_session("  admin1  ")
        assert r.admin_id == "admin1"

    def test_custom_ttl(self):
        r = svc.create_session("admin1", ttl_hours=24)
        assert r.ok
        expires = datetime.fromisoformat(r.expires_at)
        assert expires > datetime.now(UTC) + timedelta(hours=23)

    def test_default_role_viewer(self):
        r = svc.create_session("admin1")
        assert r.role == "viewer"

    def test_expires_at_set(self):
        r = svc.create_session("admin1")
        assert r.expires_at != ""


class TestBuildSessionDict:
    def test_contains_required_fields(self):
        r = svc.create_session("admin1", "admin")
        d = svc.build_session_dict(r, ip_address="127.0.0.1", user_agent="TestBrowser")
        assert d["session_id_hash"] == r.session_id_hash
        assert d["admin_id"] == "admin1"
        assert d["role"] == "admin"
        assert d["status"] == "active"
        assert d["ip_address"] == "127.0.0.1"
        assert d["user_agent"] == "TestBrowser"
        assert d["last_seen_at"] != ""

    def test_truncates_user_agent(self):
        r = svc.create_session("admin1")
        d = svc.build_session_dict(r, user_agent="x" * 1000)
        assert len(d["user_agent"]) == 512

    def test_truncates_ip(self):
        r = svc.create_session("admin1")
        d = svc.build_session_dict(r, ip_address="x" * 100)
        assert len(d["ip_address"]) == 45


class TestValidateSession:
    def _active_session(self, **overrides):
        base = {
            "admin_id": "admin1",
            "role": "admin",
            "status": "active",
            "session_id_hash": "abc123",
            "expires_at": (datetime.now(UTC) + timedelta(hours=12)).isoformat(),
        }
        base.update(overrides)
        return base

    def test_active_valid(self):
        r = svc.validate_session(self._active_session())
        assert r.ok
        assert r.admin_id == "admin1"
        assert r.role == "admin"
        assert r.status == "active"

    def test_none_session(self):
        r = svc.validate_session(None)
        assert not r.ok
        assert "not_found" in r.error

    def test_expired(self):
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        r = svc.validate_session(self._active_session(expires_at=past))
        assert not r.ok
        assert "expired" in r.error

    def test_revoked(self):
        r = svc.validate_session(self._active_session(status="revoked"))
        assert not r.ok
        assert "revoked" in r.error

    def test_replaced(self):
        r = svc.validate_session(self._active_session(status="replaced"))
        assert not r.ok
        assert "replaced" in r.error

    def test_expired_status(self):
        r = svc.validate_session(self._active_session(status="expired"))
        assert not r.ok

    def test_custom_now(self):
        future = datetime.now(UTC) + timedelta(hours=24)
        session = self._active_session(
            expires_at=(datetime.now(UTC) + timedelta(hours=12)).isoformat(),
        )
        r = svc.validate_session(session, now=future)
        assert not r.ok
        assert "expired" in r.error

    def test_datetime_expires_at(self):
        session = self._active_session(
            expires_at=datetime.now(UTC) + timedelta(hours=12),
        )
        r = svc.validate_session(session)
        assert r.ok

    def test_naive_datetime_treated_as_utc(self):
        session = self._active_session(
            expires_at=(datetime.now(UTC) + timedelta(hours=12)).replace(tzinfo=None).isoformat(),
        )
        r = svc.validate_session(session)
        assert r.ok


class TestBuildRevokeDict:
    def test_revoke(self):
        d = svc.build_revoke_dict("admin1")
        assert d["status"] == "revoked"
        assert d["revoked_at"] != ""


class TestBuildReplaceDict:
    def test_replace(self):
        d = svc.build_replace_dict()
        assert d["status"] == "replaced"
        assert d["revoked_at"] != ""


class TestBuildTouchDict:
    def test_touch(self):
        d = svc.build_touch_dict()
        assert "last_seen_at" in d
        assert d["last_seen_at"] != ""


class TestRecordLoginAttempt:
    def test_success(self):
        d = svc.record_login_attempt("admin1", "127.0.0.1", "success")
        assert d["admin_id"] == "admin1"
        assert d["status"] == "success"

    def test_failed(self):
        d = svc.record_login_attempt("admin1", status="failed", reason="bad creds")
        assert d["status"] == "failed"

    def test_blocked(self):
        d = svc.record_login_attempt(status="blocked")
        assert d["status"] == "blocked"

    def test_invalid_status_defaults_failed(self):
        d = svc.record_login_attempt(status="hack")
        assert d["status"] == "failed"

    def test_reason_sanitized(self):
        d = svc.record_login_attempt(reason="sk-secret123 failed")
        assert "sk-" not in d["reason"]

    def test_truncates_fields(self):
        d = svc.record_login_attempt(admin_id="x" * 200, ip_address="y" * 100)
        assert len(d["admin_id"]) <= 100
        assert len(d["ip_address"]) <= 45

    def test_metadata_sanitized(self):
        d = svc.record_login_attempt(metadata={"tok": "sk-secret"})
        assert "[REDACTED]" in d["metadata_json"]["tok"]


class TestIsLoginBlocked:
    def test_not_blocked(self):
        r = svc.is_login_blocked(0, max_attempts=5)
        assert r.ok
        assert not r.blocked
        assert r.remaining_attempts == 5

    def test_few_attempts(self):
        r = svc.is_login_blocked(3, max_attempts=5)
        assert r.ok
        assert r.remaining_attempts == 2

    def test_at_limit(self):
        r = svc.is_login_blocked(5, max_attempts=5)
        assert not r.ok
        assert r.blocked
        assert r.remaining_attempts == 0

    def test_over_limit(self):
        r = svc.is_login_blocked(10, max_attempts=5)
        assert r.blocked


class TestBuildCookieSettings:
    def test_defaults(self):
        c = svc.build_cookie_settings()
        assert c.name == "vp_admin_session"
        assert c.httponly is True
        assert c.secure is True
        assert c.samesite == "lax"
        assert c.path == "/"
        assert c.max_age == 43200

    def test_custom(self):
        c = svc.build_cookie_settings(
            cookie_name="custom",
            ttl_hours=24,
            secure=False,
            httponly=False,
            samesite="strict",
        )
        assert c.name == "custom"
        assert c.max_age == 86400
        assert c.secure is False
        assert c.samesite == "strict"


class TestSanitizeAuthError:
    def test_empty(self):
        assert svc.sanitize_auth_error("") == ""

    def test_clean(self):
        assert svc.sanitize_auth_error("bad password") == "bad password"

    def test_token_redacted(self):
        r = svc.sanitize_auth_error("sk-secret123 failed")
        assert "sk-" not in r

    def test_bot_token_redacted(self):
        r = svc.sanitize_auth_error("1234567890:ABCdefGhIjKlMnOpQrStUvWxYz12345678")
        assert "ABCdef" not in r

    def test_truncated(self):
        assert len(svc.sanitize_auth_error("x" * 1000)) <= 500


class TestGenericLoginError:
    def test_not_empty(self):
        assert len(svc.get_generic_login_error()) > 5

    def test_no_detail(self):
        msg = svc.get_generic_login_error()
        assert "admin_id" not in msg.lower()
        assert "password" not in msg.lower()


class TestGetStatuses:
    def test_session_statuses(self):
        s = svc.get_session_statuses()
        assert "active" in s
        assert "expired" in s
        assert "revoked" in s
        assert "replaced" in s

    def test_login_statuses(self):
        s = svc.get_login_statuses()
        assert "success" in s
        assert "failed" in s
        assert "blocked" in s


class TestSanitizeSessionForResponse:
    def test_removes_hash(self):
        d = svc.sanitize_session_for_response({"session_id_hash": "abc", "admin_id": "u1"})
        assert "session_id_hash" not in d
        assert d["admin_id"] == "u1"

    def test_redacts_tokens(self):
        d = svc.sanitize_session_for_response({"note": "sk-secret123"})
        assert "[REDACTED]" in d["note"]


class TestImmutability:
    def test_session_create_result_frozen(self):
        import pytest

        from core.services.admin_auth_service import SessionCreateResult

        r = SessionCreateResult(ok=True)
        with pytest.raises(AttributeError):
            r.ok = False  # type: ignore[misc]

    def test_session_validate_result_frozen(self):
        import pytest

        from core.services.admin_auth_service import SessionValidateResult

        r = SessionValidateResult()
        with pytest.raises(AttributeError):
            r.ok = True  # type: ignore[misc]

    def test_login_attempt_result_frozen(self):
        import pytest

        from core.services.admin_auth_service import LoginAttemptResult

        r = LoginAttemptResult()
        with pytest.raises(AttributeError):
            r.ok = True  # type: ignore[misc]

    def test_cookie_settings_frozen(self):
        import pytest

        c = CookieSettings()
        with pytest.raises(AttributeError):
            c.name = "x"  # type: ignore[misc]
