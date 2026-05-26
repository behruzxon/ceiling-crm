"""
core.services.admin_auth_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin authentication, session management, login attempt tracking.
Pure validation + deterministic helpers. No I/O in static methods.
"""
from __future__ import annotations
import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_SESSION_STATUSES = ("active", "expired", "revoked", "replaced")
_LOGIN_STATUSES = ("success", "failed", "blocked")


@dataclass(frozen=True)
class SessionCreateResult:
    ok: bool = False
    session_id: str = ""
    session_id_hash: str = ""
    admin_id: str = ""
    role: str = ""
    expires_at: str = ""
    error: str = ""


@dataclass(frozen=True)
class SessionValidateResult:
    ok: bool = False
    admin_id: str = ""
    role: str = ""
    session_id_hash: str = ""
    status: str = ""
    error: str = ""


@dataclass(frozen=True)
class SessionRevokeResult:
    ok: bool = False
    error: str = ""


@dataclass(frozen=True)
class LoginAttemptResult:
    ok: bool = False
    blocked: bool = False
    remaining_attempts: int = 0
    error: str = ""


@dataclass(frozen=True)
class CookieSettings:
    name: str = "vp_admin_session"
    httponly: bool = True
    secure: bool = True
    samesite: str = "lax"
    max_age: int = 43200
    path: str = "/"


class AdminAuthService:
    """Admin authentication and session management."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    @staticmethod
    def generate_session_id() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_session_id(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()

    @staticmethod
    def create_session(
        admin_id: str,
        role: str = "viewer",
        ip_address: str = "",
        user_agent: str = "",
        ttl_hours: int = 12,
    ) -> SessionCreateResult:
        if not admin_id or not admin_id.strip():
            return SessionCreateResult(ok=False, error="admin_id required")
        session_id = AdminAuthService.generate_session_id()
        session_hash = AdminAuthService.hash_session_id(session_id)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=ttl_hours)
        return SessionCreateResult(
            ok=True,
            session_id=session_id,
            session_id_hash=session_hash,
            admin_id=admin_id.strip(),
            role=role,
            expires_at=expires.isoformat(),
        )

    @staticmethod
    def build_session_dict(
        result: SessionCreateResult,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        return {
            "session_id_hash": result.session_id_hash,
            "admin_id": result.admin_id,
            "role": result.role,
            "status": "active",
            "ip_address": ip_address[:45] if ip_address else "",
            "user_agent": user_agent[:512] if user_agent else "",
            "expires_at": result.expires_at,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def validate_session(
        session_dict: dict[str, Any] | None,
        now: datetime | None = None,
    ) -> SessionValidateResult:
        if session_dict is None:
            return SessionValidateResult(ok=False, error="session_not_found")
        status = session_dict.get("status", "")
        if status != "active":
            return SessionValidateResult(
                ok=False, error=f"session_{status}",
                status=status,
                admin_id=session_dict.get("admin_id", ""),
            )
        expires_at_str = session_dict.get("expires_at", "")
        if expires_at_str:
            try:
                if isinstance(expires_at_str, datetime):
                    expires_at = expires_at_str
                else:
                    expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                check_time = now or datetime.now(timezone.utc)
                if check_time > expires_at:
                    return SessionValidateResult(
                        ok=False, error="session_expired",
                        status="expired",
                        admin_id=session_dict.get("admin_id", ""),
                    )
            except (ValueError, TypeError):
                return SessionValidateResult(ok=False, error="invalid_expires_at")
        return SessionValidateResult(
            ok=True,
            admin_id=session_dict.get("admin_id", ""),
            role=session_dict.get("role", "viewer"),
            session_id_hash=session_dict.get("session_id_hash", ""),
            status="active",
        )

    @staticmethod
    def build_revoke_dict(
        actor_admin_id: str = "",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "status": "revoked",
            "revoked_at": now,
        }

    @staticmethod
    def build_replace_dict() -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "status": "replaced",
            "revoked_at": now,
        }

    @staticmethod
    def build_touch_dict() -> dict[str, Any]:
        return {"last_seen_at": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def record_login_attempt(
        admin_id: str = "",
        ip_address: str = "",
        status: str = "success",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in _LOGIN_STATUSES:
            status = "failed"
        return {
            "admin_id": admin_id[:100] if admin_id else "",
            "ip_address": ip_address[:45] if ip_address else "",
            "status": status,
            "reason": AdminAuthService.sanitize_auth_error(reason) if reason else "",
            "metadata_json": AdminAuthService._sanitize_metadata(metadata),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def is_login_blocked(
        failed_count: int,
        max_attempts: int = 5,
    ) -> LoginAttemptResult:
        if failed_count >= max_attempts:
            return LoginAttemptResult(
                ok=False, blocked=True, remaining_attempts=0,
                error="too_many_failed_attempts",
            )
        return LoginAttemptResult(
            ok=True, blocked=False,
            remaining_attempts=max(0, max_attempts - failed_count),
        )

    @staticmethod
    def build_cookie_settings(
        cookie_name: str = "vp_admin_session",
        ttl_hours: int = 12,
        secure: bool = True,
        httponly: bool = True,
        samesite: str = "lax",
    ) -> CookieSettings:
        return CookieSettings(
            name=cookie_name,
            httponly=httponly,
            secure=secure,
            samesite=samesite,
            max_age=ttl_hours * 3600,
            path="/",
        )

    @staticmethod
    def sanitize_auth_error(error: str) -> str:
        if not error:
            return ""
        error = _TOKEN_RE.sub("[REDACTED]", error)
        error = _BOT_TOKEN_RE.sub("[REDACTED]", error)
        return error[:500]

    @staticmethod
    def get_generic_login_error() -> str:
        return "Login yoki parol noto'g'ri"

    @staticmethod
    def get_session_statuses() -> tuple[str, ...]:
        return _SESSION_STATUSES

    @staticmethod
    def get_login_statuses() -> tuple[str, ...]:
        return _LOGIN_STATUSES

    @staticmethod
    def sanitize_session_for_response(session_dict: dict[str, Any]) -> dict[str, Any]:
        safe = dict(session_dict)
        safe.pop("session_id_hash", None)
        for key in list(safe.keys()):
            val = safe[key]
            if isinstance(val, str) and _TOKEN_RE.search(val):
                safe[key] = "[REDACTED]"
        return safe

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if metadata is None:
            return None
        safe: dict[str, Any] = {}
        for key, val in metadata.items():
            if isinstance(val, str):
                val = _TOKEN_RE.sub("[REDACTED]", val)
                val = _BOT_TOKEN_RE.sub("[REDACTED]", val)
            safe[key] = val
        return safe
