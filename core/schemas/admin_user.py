"""Frozen dataclasses for admin user and audit log schemas."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AdminUserRecord:
    id: int = 0
    admin_id: str = ""
    display_name: str = ""
    role: str = "viewer"
    is_active: bool = True
    is_super_owner: bool = False
    permissions_override_json: dict | None = None
    last_seen_at: str = ""
    created_by: str = ""
    updated_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    disabled_at: str = ""


@dataclass(frozen=True)
class AdminUserCreateRequest:
    admin_id: str = ""
    display_name: str = ""
    role: str = "viewer"
    is_super_owner: bool = False
    permissions_override_json: dict | None = None
    created_by: str = ""


@dataclass(frozen=True)
class AdminUserUpdateRequest:
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    permissions_override_json: dict | None = None
    updated_by: str = ""


@dataclass(frozen=True)
class AdminAuditEntry:
    id: int = 0
    actor_admin_id: str = ""
    actor_role: str = ""
    action: str = ""
    target_type: str = ""
    target_id: str = ""
    status: str = "success"
    reason: str = ""
    metadata_json: dict | None = None
    created_at: str = ""


@dataclass(frozen=True)
class AdminUserServiceResult:
    ok: bool = False
    admin: AdminUserRecord | None = None
    error: str = ""
    warnings: list[str] = field(default_factory=list)
