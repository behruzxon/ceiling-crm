"""Frozen dataclasses for admin authentication and session schemas."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdminLoginRequest:
    admin_id: str = ""
    secret_or_token: str = ""
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True)
class AdminLoginResult:
    ok: bool = False
    session_id: str = ""
    admin_id: str = ""
    role: str = ""
    error: str = ""
    blocked: bool = False
    remaining_attempts: int = 0


@dataclass(frozen=True)
class AdminSessionRecord:
    id: int = 0
    session_id_hash: str = ""
    admin_id: str = ""
    role: str = ""
    status: str = "active"
    ip_address: str = ""
    user_agent: str = ""
    created_at: str = ""
    last_seen_at: str = ""
    expires_at: str = ""
    revoked_at: str = ""
    metadata_json: dict | None = None


@dataclass(frozen=True)
class AdminSessionPrincipal:
    admin_id: str = ""
    role: str = "viewer"
    session_id_hash: str = ""
    is_authenticated: bool = False
    source: str = ""
    permissions_override: dict | None = None


@dataclass(frozen=True)
class AdminCSRFToken:
    token: str = ""
    session_id_hash: str = ""
    created_at: str = ""
    is_valid: bool = False


@dataclass(frozen=True)
class AdminLoginAttemptRecord:
    id: int = 0
    admin_id: str = ""
    ip_address: str = ""
    status: str = ""
    reason: str = ""
    created_at: str = ""
    metadata_json: dict | None = None


@dataclass(frozen=True)
class AdminLogoutResult:
    ok: bool = False
    session_revoked: bool = False
    error: str = ""
