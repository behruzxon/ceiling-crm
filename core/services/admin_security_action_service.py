"""
core.services.admin_security_action_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Security actions: session revoke, admin disable, IP rules.
Pure validation + dict builders. No direct DB I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$")
_RULE_TYPES = ("allow", "block", "watch")


@dataclass(frozen=True)
class SecurityActionResult:
    ok: bool = False
    action: str = ""
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IPEvaluationResult:
    ip: str = ""
    decision: str = "unknown"
    matched_rule_type: str = ""
    enforcement_enabled: bool = False


class AdminSecurityActionService:
    """Security action validation and dict builders."""

    @staticmethod
    def check_actions_enabled(enabled: bool = False) -> SecurityActionResult:
        if not enabled:
            return SecurityActionResult(ok=False, error="security_actions_disabled")
        return SecurityActionResult(ok=True)

    @staticmethod
    def require_confirmation(confirm: bool, require: bool = True) -> SecurityActionResult:
        if require and not confirm:
            return SecurityActionResult(ok=False, error="confirmation_required")
        return SecurityActionResult(ok=True)

    @staticmethod
    def prevent_self_lockout(actor_admin_id: str, target_admin_id: str) -> SecurityActionResult:
        if actor_admin_id and target_admin_id and actor_admin_id == target_admin_id:
            return SecurityActionResult(ok=False, error="cannot_act_on_self")
        return SecurityActionResult(ok=True)

    @staticmethod
    def prevent_last_owner_disable(
        target_role: str,
        target_is_super_owner: bool,
        active_owner_count: int,
    ) -> SecurityActionResult:
        if target_is_super_owner:
            return SecurityActionResult(ok=False, error="cannot_disable_super_owner")
        if target_role == "owner" and active_owner_count <= 1:
            return SecurityActionResult(ok=False, error="cannot_disable_last_owner")
        return SecurityActionResult(ok=True)

    # ── Session Revoke ─────────────────────────────────────────────────

    @staticmethod
    def validate_revoke_session(
        session_dict: dict[str, Any] | None,
        actor_admin_id: str = "",
        confirm: bool = False,
        actions_enabled: bool = False,
        require_confirmation: bool = True,
    ) -> SecurityActionResult:
        check = AdminSecurityActionService.check_actions_enabled(actions_enabled)
        if not check.ok:
            return check
        check = AdminSecurityActionService.require_confirmation(confirm, require_confirmation)
        if not check.ok:
            return check
        if session_dict is None:
            return SecurityActionResult(
                ok=False, action="session.revoke", error="session_not_found"
            )
        if session_dict.get("status") == "revoked":
            return SecurityActionResult(
                ok=False, action="session.revoke", error="session_already_revoked"
            )
        if session_dict.get("status") == "expired":
            return SecurityActionResult(
                ok=False, action="session.revoke", error="session_already_expired"
            )
        return SecurityActionResult(ok=True, action="session.revoke")

    @staticmethod
    def build_revoke_session_dict() -> dict[str, Any]:
        return {
            "status": "revoked",
            "revoked_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def build_revoke_all_filter(
        target_admin_id: str,
        exclude_session_hash: str = "",
    ) -> dict[str, Any]:
        f: dict[str, Any] = {
            "admin_id": target_admin_id,
            "status": "active",
        }
        if exclude_session_hash:
            f["exclude_hash"] = exclude_session_hash
        return f

    # ── Admin Disable/Enable ───────────────────────────────────────────

    @staticmethod
    def validate_disable_admin(
        target_dict: dict[str, Any] | None,
        actor_admin_id: str = "",
        confirm: bool = False,
        actions_enabled: bool = False,
        require_confirmation: bool = True,
        active_owner_count: int = 0,
    ) -> SecurityActionResult:
        check = AdminSecurityActionService.check_actions_enabled(actions_enabled)
        if not check.ok:
            return check
        check = AdminSecurityActionService.require_confirmation(confirm, require_confirmation)
        if not check.ok:
            return check
        if target_dict is None:
            return SecurityActionResult(ok=False, action="admin.disable", error="admin_not_found")
        target_id = target_dict.get("admin_id", "")
        check = AdminSecurityActionService.prevent_self_lockout(actor_admin_id, target_id)
        if not check.ok:
            return SecurityActionResult(ok=False, action="admin.disable", error=check.error)
        if not target_dict.get("is_active", True):
            return SecurityActionResult(
                ok=False, action="admin.disable", error="admin_already_disabled"
            )
        check = AdminSecurityActionService.prevent_last_owner_disable(
            target_dict.get("role", "viewer"),
            target_dict.get("is_super_owner", False),
            active_owner_count,
        )
        if not check.ok:
            return SecurityActionResult(ok=False, action="admin.disable", error=check.error)
        return SecurityActionResult(ok=True, action="admin.disable")

    @staticmethod
    def validate_enable_admin(
        target_dict: dict[str, Any] | None,
        actions_enabled: bool = False,
        confirm: bool = False,
        require_confirmation: bool = True,
    ) -> SecurityActionResult:
        check = AdminSecurityActionService.check_actions_enabled(actions_enabled)
        if not check.ok:
            return check
        check = AdminSecurityActionService.require_confirmation(confirm, require_confirmation)
        if not check.ok:
            return check
        if target_dict is None:
            return SecurityActionResult(ok=False, action="admin.enable", error="admin_not_found")
        if target_dict.get("is_active", True):
            return SecurityActionResult(
                ok=False, action="admin.enable", error="admin_already_active"
            )
        return SecurityActionResult(ok=True, action="admin.enable")

    # ── IP Rules ───────────────────────────────────────────────────────

    @staticmethod
    def validate_ip_pattern(ip_pattern: str) -> SecurityActionResult:
        if not ip_pattern or not ip_pattern.strip():
            return SecurityActionResult(ok=False, error="ip_pattern_required")
        ip = ip_pattern.strip()
        if not _IP_RE.match(ip):
            return SecurityActionResult(ok=False, error="invalid_ip_pattern")
        parts = ip.split("/")[0].split(".")
        for part in parts:
            if int(part) > 255:
                return SecurityActionResult(ok=False, error="invalid_ip_octet")
        return SecurityActionResult(ok=True)

    @staticmethod
    def validate_rule_type(rule_type: str) -> SecurityActionResult:
        if rule_type not in _RULE_TYPES:
            return SecurityActionResult(
                ok=False, error=f"invalid_rule_type, must be one of {_RULE_TYPES}"
            )
        return SecurityActionResult(ok=True)

    @staticmethod
    def build_ip_rule_dict(
        ip_pattern: str,
        rule_type: str,
        reason: str = "",
        created_by: str = "",
    ) -> dict[str, Any]:
        return {
            "ip_pattern": ip_pattern.strip(),
            "rule_type": rule_type,
            "reason": AdminSecurityActionService.sanitize_reason(reason),
            "is_active": True,
            "created_by": created_by[:100] if created_by else "",
            "created_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def build_disable_ip_rule_dict(updated_by: str = "") -> dict[str, Any]:
        return {
            "is_active": False,
            "disabled_at": datetime.now(UTC).isoformat(),
            "updated_by": updated_by[:100] if updated_by else "",
            "updated_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def evaluate_ip_access(
        ip_address: str,
        rules: list[dict[str, Any]],
        enforcement_enabled: bool = False,
    ) -> IPEvaluationResult:
        if not rules:
            return IPEvaluationResult(
                ip=ip_address, decision="unknown", enforcement_enabled=enforcement_enabled
            )
        for rule in rules:
            if not rule.get("is_active", False):
                continue
            pattern = rule.get("ip_pattern", "")
            if "/" in pattern:
                if ip_address.startswith(pattern.split("/")[0].rsplit(".", 1)[0]):
                    return IPEvaluationResult(
                        ip=ip_address,
                        decision=rule["rule_type"] if enforcement_enabled else "advisory",
                        matched_rule_type=rule["rule_type"],
                        enforcement_enabled=enforcement_enabled,
                    )
            elif pattern == ip_address:
                return IPEvaluationResult(
                    ip=ip_address,
                    decision=rule["rule_type"] if enforcement_enabled else "advisory",
                    matched_rule_type=rule["rule_type"],
                    enforcement_enabled=enforcement_enabled,
                )
        return IPEvaluationResult(
            ip=ip_address, decision="unknown", enforcement_enabled=enforcement_enabled
        )

    @staticmethod
    def get_rule_types() -> tuple[str, ...]:
        return _RULE_TYPES

    # ── Audit ──────────────────────────────────────────────────────────

    @staticmethod
    def build_action_audit(
        actor_admin_id: str,
        action: str,
        target_type: str = "",
        target_id: str = "",
        status: str = "success",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "actor_admin_id": actor_admin_id[:100] if actor_admin_id else "",
            "action": action[:80] if action else "",
            "target_type": target_type[:50] if target_type else "",
            "target_id": target_id[:100] if target_id else "",
            "status": status,
            "reason": AdminSecurityActionService.sanitize_reason(reason),
            "metadata_json": AdminSecurityActionService._sanitize_metadata(metadata),
            "created_at": datetime.now(UTC).isoformat(),
        }

    # ── Sanitization ───────────────────────────────────────────────────

    @staticmethod
    def sanitize_reason(reason: str) -> str:
        if not reason:
            return ""
        reason = _TOKEN_RE.sub("[REDACTED]", reason)
        reason = _BOT_TOKEN_RE.sub("[REDACTED]", reason)
        return reason[:500]

    @staticmethod
    def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
        safe = dict(result)
        safe.pop("session_id_hash", None)
        safe.pop("session_id", None)
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
