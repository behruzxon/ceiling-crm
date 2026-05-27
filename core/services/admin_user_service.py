"""
core.services.admin_user_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin user CRUD with owner lockout protection. Pure validation + session ops.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_VALID_ROLES = ("owner", "admin", "operator", "analyst", "viewer")
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,100}$")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


@dataclass(frozen=True)
class AdminUserResult:
    ok: bool = False
    user: dict[str, Any] | None = None
    error: str = ""
    warnings: list[str] = field(default_factory=list)


class AdminUserService:
    """Admin user management with owner lockout protection."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    @staticmethod
    def validate_admin_id(admin_id: str) -> str | None:
        if not admin_id or not admin_id.strip():
            return "admin_id is required"
        if not _SAFE_ID_RE.match(admin_id.strip()):
            return "admin_id contains invalid characters"
        return None

    @staticmethod
    def validate_role(role: str) -> str | None:
        if role not in _VALID_ROLES:
            return f"invalid role: {role}, must be one of {_VALID_ROLES}"
        return None

    @staticmethod
    def validate_display_name(name: str) -> str | None:
        if name and len(name) > 128:
            return "display_name too long (max 128)"
        if name and _TOKEN_RE.search(name):
            return "display_name contains suspicious pattern"
        return None

    @staticmethod
    def can_create(
        actor_role: str,
        target_role: str,
    ) -> AdminUserResult:
        if actor_role not in ("owner", "admin"):
            return AdminUserResult(ok=False, error="only owner/admin can create users")
        if target_role == "owner" and actor_role != "owner":
            return AdminUserResult(ok=False, error="only owner can create owners")
        return AdminUserResult(ok=True)

    @staticmethod
    def can_update_role(
        actor_role: str,
        target_current_role: str,
        new_role: str,
    ) -> AdminUserResult:
        if actor_role not in ("owner", "admin"):
            return AdminUserResult(ok=False, error="only owner/admin can change roles")
        if target_current_role == "owner" and actor_role != "owner":
            return AdminUserResult(ok=False, error="only owner can change owner role")
        if new_role == "owner" and actor_role != "owner":
            return AdminUserResult(ok=False, error="only owner can promote to owner")
        return AdminUserResult(ok=True)

    @staticmethod
    def can_disable(
        actor_role: str,
        actor_admin_id: str,
        target_admin_id: str,
        target_role: str,
        target_is_super_owner: bool,
        active_owner_count: int,
    ) -> AdminUserResult:
        if actor_role not in ("owner", "admin"):
            return AdminUserResult(ok=False, error="only owner/admin can disable users")
        if target_is_super_owner:
            return AdminUserResult(ok=False, error="cannot disable super owner")
        if target_role == "owner" and actor_role != "owner":
            return AdminUserResult(ok=False, error="only owner can disable another owner")
        if actor_admin_id == target_admin_id:
            return AdminUserResult(ok=False, error="cannot disable yourself")
        if target_role == "owner" and active_owner_count <= 1:
            return AdminUserResult(ok=False, error="cannot disable last active owner")
        return AdminUserResult(ok=True)

    @staticmethod
    def can_enable(actor_role: str) -> AdminUserResult:
        if actor_role not in ("owner", "admin"):
            return AdminUserResult(ok=False, error="only owner/admin can enable users")
        return AdminUserResult(ok=True)

    @staticmethod
    def build_create_dict(
        admin_id: str,
        display_name: str = "",
        role: str = "viewer",
        is_super_owner: bool = False,
        permissions_override: dict | None = None,
        created_by: str = "",
    ) -> dict[str, Any]:
        return {
            "admin_id": admin_id.strip(),
            "display_name": display_name[:128] if display_name else "",
            "role": role,
            "is_active": True,
            "is_super_owner": is_super_owner,
            "permissions_override_json": permissions_override,
            "created_by": created_by,
            "created_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def build_update_dict(
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        permissions_override: dict | None = None,
        updated_by: str = "",
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {"updated_by": updated_by, "updated_at": datetime.now(UTC).isoformat()}
        if display_name is not None:
            updates["display_name"] = display_name[:128]
        if role is not None:
            updates["role"] = role
        if is_active is not None:
            updates["is_active"] = is_active
            if not is_active:
                updates["disabled_at"] = datetime.now(UTC).isoformat()
            else:
                updates["disabled_at"] = None
        if permissions_override is not None:
            updates["permissions_override_json"] = permissions_override
        return updates

    @staticmethod
    def sanitize_for_response(user_dict: dict[str, Any]) -> dict[str, Any]:
        safe = dict(user_dict)
        for key in list(safe.keys()):
            val = safe[key]
            if isinstance(val, str) and _TOKEN_RE.search(val):
                safe[key] = "[REDACTED]"
        return safe

    @staticmethod
    def get_valid_roles() -> tuple[str, ...]:
        return _VALID_ROLES
