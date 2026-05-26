"""Tests for Step BJ — AdminCSRFService."""
from __future__ import annotations
from core.services.admin_csrf_service import AdminCSRFService, CSRFValidateResult

svc = AdminCSRFService


class TestGenerateCSRFToken:
    def test_not_empty(self):
        token = svc.generate_csrf_token("session_hash", "secret_key")
        assert len(token) > 10

    def test_contains_signature(self):
        token = svc.generate_csrf_token("session_hash", "secret_key")
        assert "." in token

    def test_unique(self):
        t1 = svc.generate_csrf_token("h1", "k1")
        t2 = svc.generate_csrf_token("h1", "k1")
        assert t1 != t2

    def test_no_secret_no_signature(self):
        token = svc.generate_csrf_token("h1")
        assert "." not in token

    def test_with_both_params(self):
        token = svc.generate_csrf_token("hash1", "key1")
        assert "." in token
        assert len(token) > 20


class TestValidateCSRFToken:
    def test_disabled_always_ok(self):
        r = svc.validate_csrf_token("", "", "", enabled=False)
        assert r.ok

    def test_missing_token(self):
        r = svc.validate_csrf_token("", "h1", "k1", enabled=True)
        assert not r.ok
        assert "missing" in r.error

    def test_invalid_format(self):
        r = svc.validate_csrf_token("noperiod", "h1", "k1", enabled=True)
        assert not r.ok
        assert "format" in r.error

    def test_valid_token(self):
        token = svc.generate_csrf_token("h1", "k1")
        r = svc.validate_csrf_token(token, "h1", "k1", enabled=True)
        assert r.ok

    def test_wrong_session(self):
        token = svc.generate_csrf_token("h1", "k1")
        r = svc.validate_csrf_token(token, "h2", "k1", enabled=True)
        assert not r.ok
        assert "mismatch" in r.error

    def test_wrong_key(self):
        token = svc.generate_csrf_token("h1", "k1")
        r = svc.validate_csrf_token(token, "h1", "k2", enabled=True)
        assert not r.ok

    def test_missing_secret_key(self):
        r = svc.validate_csrf_token("raw.sig", "h1", "", enabled=True)
        assert not r.ok
        assert "secret" in r.error

    def test_tampered_signature(self):
        token = svc.generate_csrf_token("h1", "k1")
        parts = token.rsplit(".", 1)
        tampered = parts[0] + ".baaaaad"
        r = svc.validate_csrf_token(tampered, "h1", "k1", enabled=True)
        assert not r.ok

    def test_whitespace_token(self):
        r = svc.validate_csrf_token("   ", "h1", "k1", enabled=True)
        assert not r.ok


class TestShouldRequireCSRF:
    def test_disabled(self):
        assert not svc.should_require_csrf("POST", "/login", enabled=False)

    def test_get_exempt(self):
        assert not svc.should_require_csrf("GET", "/page", enabled=True)

    def test_head_exempt(self):
        assert not svc.should_require_csrf("HEAD", "/page", enabled=True)

    def test_options_exempt(self):
        assert not svc.should_require_csrf("OPTIONS", "/page", enabled=True)

    def test_post_required(self):
        assert svc.should_require_csrf("POST", "/login", enabled=True)

    def test_patch_required(self):
        assert svc.should_require_csrf("PATCH", "/update", enabled=True)

    def test_delete_required(self):
        assert svc.should_require_csrf("DELETE", "/item", enabled=True)

    def test_put_required(self):
        assert svc.should_require_csrf("PUT", "/item", enabled=True)

    def test_case_insensitive(self):
        assert not svc.should_require_csrf("get", "/page", enabled=True)


class TestHashCSRFToken:
    def test_deterministic(self):
        h1 = svc.hash_csrf_token("abc")
        h2 = svc.hash_csrf_token("abc")
        assert h1 == h2

    def test_different_input(self):
        assert svc.hash_csrf_token("a") != svc.hash_csrf_token("b")

    def test_no_raw_token(self):
        token = "mysecrettoken"
        h = svc.hash_csrf_token(token)
        assert token not in h


class TestExemptSafeMethods:
    def test_returns_frozenset(self):
        s = svc.exempt_safe_methods()
        assert isinstance(s, frozenset)
        assert "GET" in s
        assert "HEAD" in s
        assert "OPTIONS" in s
        assert "POST" not in s


class TestSanitizeCSRFError:
    def test_empty(self):
        assert svc.sanitize_csrf_error("") == ""

    def test_clean(self):
        assert svc.sanitize_csrf_error("token missing") == "token missing"

    def test_redacts_token(self):
        r = svc.sanitize_csrf_error("sk-secret123 in token")
        assert "sk-" not in r

    def test_truncated(self):
        assert len(svc.sanitize_csrf_error("x" * 500)) <= 300


class TestImmutability:
    def test_result_frozen(self):
        import pytest
        r = CSRFValidateResult(ok=True)
        with pytest.raises(AttributeError):
            r.ok = False  # type: ignore[misc]
