"""Frozen dataclasses for admin security action schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdminSecurityActionRequest:
    action: str = ""
    actor_admin_id: str = ""
    target_type: str = ""
    target_id: str = ""
    reason: str = ""
    confirm: bool = False


@dataclass(frozen=True)
class AdminSecurityActionResult:
    ok: bool = False
    action: str = ""
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    audit_entry: dict[str, Any] | None = None


@dataclass(frozen=True)
class AdminSessionRevokeRequest:
    session_record_id: int = 0
    actor_admin_id: str = ""
    reason: str = ""
    confirm: bool = False


@dataclass(frozen=True)
class AdminUserDisableRequest:
    target_admin_id: str = ""
    actor_admin_id: str = ""
    reason: str = ""
    confirm: bool = False


@dataclass(frozen=True)
class AdminIPRuleCreate:
    ip_pattern: str = ""
    rule_type: str = "block"
    reason: str = ""
    created_by: str = ""


@dataclass(frozen=True)
class AdminIPRuleUpdate:
    is_active: bool | None = None
    reason: str | None = None
    updated_by: str = ""


@dataclass(frozen=True)
class AdminIPRuleResponse:
    id: int = 0
    ip_pattern: str = ""
    rule_type: str = ""
    reason: str = ""
    is_active: bool = True
    created_by: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class AdminSecurityActionAuditItem:
    actor_admin_id: str = ""
    action: str = ""
    target_type: str = ""
    target_id: str = ""
    status: str = "success"
    reason: str = ""
    created_at: str = ""
