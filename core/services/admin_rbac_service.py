"""
core.services.admin_rbac_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Role-based access control for admin platform. Pure functions.
Backward-compatible: when RBAC disabled, existing single-admin works.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

_ROLES = ("owner", "admin", "operator", "analyst", "viewer")

_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({
        "crm.view", "crm.view_sensitive", "crm.edit", "crm.notes", "crm.tags",
        "crm.tasks", "crm.reply", "crm.export", "crm.export_sensitive",
        "crm.reports.view", "crm.reports.generate", "crm.reports.approve_delivery",
        "crm.reports.send_delivery",
        "agent.view", "agent.metrics", "agent.settings.view", "agent.settings.mutate",
        "agent.rollout.preview", "agent.rollout.apply",
        "agent.execution.view", "agent.execution.approve", "agent.execution.reject",
        "admin.users", "admin.permissions", "system.health", "system.audit",
        "security.view", "security.manage", "security.sessions.revoke",
        "security.admin.disable", "security.ip_rules.manage",
        "crm.merge",
        "crm.campaigns.view", "crm.campaigns.manage", "crm.campaigns.approve",
        "crm.campaigns.send",
    }),
    "admin": frozenset({
        "crm.view", "crm.view_sensitive", "crm.edit", "crm.notes", "crm.tags",
        "crm.tasks", "crm.reply", "crm.export", "crm.export_sensitive",
        "crm.reports.view", "crm.reports.generate", "crm.reports.approve_delivery",
        "crm.reports.send_delivery",
        "agent.view", "agent.metrics", "agent.settings.view", "agent.settings.mutate",
        "agent.rollout.preview", "agent.rollout.apply",
        "agent.execution.view", "agent.execution.approve", "agent.execution.reject",
        "system.health", "system.audit",
        "security.view", "security.sessions.revoke", "security.ip_rules.manage",
        "crm.merge",
        "crm.campaigns.view", "crm.campaigns.manage", "crm.campaigns.approve",
        "crm.campaigns.send",
    }),
    "operator": frozenset({
        "crm.view", "crm.notes", "crm.tags", "crm.tasks", "crm.reply",
        "crm.reports.view",
        "agent.view", "agent.metrics", "agent.execution.view",
    }),
    "analyst": frozenset({
        "crm.view", "crm.export", "crm.reports.view",
        "agent.view", "agent.metrics",
    }),
    "viewer": frozenset({
        "crm.view", "crm.reports.view", "agent.view",
    }),
}


@dataclass(frozen=True)
class PermissionCheckResult:
    allowed: bool = False
    role: str = "viewer"
    permission: str = ""
    reason: str = ""


class AdminRBACService:
    """Pure RBAC logic. Config-driven roles."""

    @staticmethod
    def is_valid_role(role: str) -> bool:
        return role in _ROLES

    @staticmethod
    def get_permissions_for_role(role: str) -> frozenset[str]:
        return _ROLE_PERMISSIONS.get(role, frozenset())

    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        perms = _ROLE_PERMISSIONS.get(role, frozenset())
        return permission in perms

    @staticmethod
    def check_permission(
        role: str, permission: str,
    ) -> PermissionCheckResult:
        allowed = AdminRBACService.has_permission(role, permission)
        reason = "" if allowed else f"{role} does not have {permission}"
        return PermissionCheckResult(
            allowed=allowed, role=role, permission=permission, reason=reason,
        )

    @staticmethod
    def get_role_for_admin(
        admin_id: str,
        owner_ids: str = "",
        admin_ids: str = "",
        operator_ids: str = "",
        analyst_ids: str = "",
        viewer_ids: str = "",
        default_role: str = "admin",
    ) -> str:
        aid = str(admin_id).strip()
        for ids_str, role in [
            (owner_ids, "owner"), (admin_ids, "admin"),
            (operator_ids, "operator"), (analyst_ids, "analyst"),
            (viewer_ids, "viewer"),
        ]:
            if aid in [x.strip() for x in ids_str.split(",") if x.strip()]:
                return role
        return default_role

    @staticmethod
    def build_role_matrix() -> dict[str, list[str]]:
        return {role: sorted(perms) for role, perms in _ROLE_PERMISSIONS.items()}

    @staticmethod
    def build_principal_summary(
        role: str,
    ) -> dict[str, Any]:
        perms = _ROLE_PERMISSIONS.get(role, frozenset())
        return {
            "role": role,
            "permissions": sorted(perms),
            "can_view_sensitive": "crm.view_sensitive" in perms,
            "can_reply": "crm.reply" in perms,
            "can_export": "crm.export" in perms,
            "can_export_sensitive": "crm.export_sensitive" in perms,
            "can_mutate_settings": "agent.settings.mutate" in perms,
            "can_apply_rollout": "agent.rollout.apply" in perms,
            "can_approve_delivery": "crm.reports.approve_delivery" in perms,
        }

    @staticmethod
    def resolve_role_with_db(
        admin_id: str,
        db_user: dict | None,
        db_rbac_enabled: bool = False,
        fallback_to_env: bool = True,
        owner_ids: str = "",
        admin_ids: str = "",
        operator_ids: str = "",
        analyst_ids: str = "",
        viewer_ids: str = "",
        default_role: str = "admin",
    ) -> tuple[str, str]:
        """Resolve role from DB first, then env fallback.

        Returns (role, source) where source is "db" or "env".
        """
        if db_rbac_enabled and db_user is not None:
            if db_user.get("is_active", False):
                return db_user.get("role", "viewer"), "db"
        if fallback_to_env or not db_rbac_enabled:
            env_role = AdminRBACService.get_role_for_admin(
                admin_id,
                owner_ids=owner_ids,
                admin_ids=admin_ids,
                operator_ids=operator_ids,
                analyst_ids=analyst_ids,
                viewer_ids=viewer_ids,
                default_role=default_role,
            )
            return env_role, "env"
        return default_role, "env"

    @staticmethod
    def get_effective_permissions(
        role: str,
        permissions_override: dict | None = None,
    ) -> frozenset[str]:
        base = _ROLE_PERMISSIONS.get(role, frozenset())
        if not permissions_override:
            return base
        result = set(base)
        for perm, allowed in permissions_override.items():
            if allowed:
                result.add(perm)
            else:
                result.discard(perm)
        return frozenset(result)

    @staticmethod
    def check_permission_with_override(
        role: str,
        permission: str,
        permissions_override: dict | None = None,
    ) -> PermissionCheckResult:
        effective = AdminRBACService.get_effective_permissions(role, permissions_override)
        allowed = permission in effective
        reason = "" if allowed else f"{role} does not have {permission}"
        return PermissionCheckResult(
            allowed=allowed, role=role, permission=permission, reason=reason,
        )

    @staticmethod
    def explain_denial(permission: str, role: str) -> str:
        return f"Ruxsat yo'q: {permission} — sizning rolingiz: {role}"
