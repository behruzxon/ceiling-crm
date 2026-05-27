"""
core.services.admin_csrf_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CSRF token generation and validation. Pure functions.
Default disabled by config — foundation only.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class CSRFValidateResult:
    ok: bool = False
    error: str = ""


class AdminCSRFService:
    """CSRF token management. Foundation — disabled by default."""

    @staticmethod
    def generate_csrf_token(session_id_hash: str, secret_key: str = "") -> str:
        raw = secrets.token_urlsafe(32)
        if session_id_hash and secret_key:
            sig = hmac.new(
                secret_key.encode("utf-8"),
                f"{session_id_hash}:{raw}".encode(),
                hashlib.sha256,
            ).hexdigest()[:16]
            return f"{raw}.{sig}"
        return raw

    @staticmethod
    def validate_csrf_token(
        token: str,
        session_id_hash: str,
        secret_key: str = "",
        enabled: bool = False,
    ) -> CSRFValidateResult:
        if not enabled:
            return CSRFValidateResult(ok=True)
        if not token or not token.strip():
            return CSRFValidateResult(ok=False, error="csrf_token_missing")
        if "." not in token:
            return CSRFValidateResult(ok=False, error="csrf_token_invalid_format")
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return CSRFValidateResult(ok=False, error="csrf_token_invalid_format")
        raw, provided_sig = parts
        if not secret_key:
            return CSRFValidateResult(ok=False, error="csrf_secret_missing")
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            f"{session_id_hash}:{raw}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        if not hmac.compare_digest(provided_sig, expected_sig):
            return CSRFValidateResult(ok=False, error="csrf_token_mismatch")
        return CSRFValidateResult(ok=True)

    @staticmethod
    def should_require_csrf(method: str, path: str = "", enabled: bool = False) -> bool:
        if not enabled:
            return False
        return method.upper() not in _SAFE_METHODS

    @staticmethod
    def hash_csrf_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def exempt_safe_methods() -> frozenset[str]:
        return _SAFE_METHODS

    @staticmethod
    def sanitize_csrf_error(error: str) -> str:
        if not error:
            return ""
        error = _TOKEN_RE.sub("[REDACTED]", error)
        return error[:300]
