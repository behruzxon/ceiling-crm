"""
core.services.admin_audit_log_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin audit log recording — actions, denials, failures. Pure functions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_PHONE_RE = re.compile(r"\+?\d{9,15}")

_VALID_STATUSES = ("success", "denied", "failed", "warning")
_VALID_ACTIONS = (
    "admin_user.create", "admin_user.update", "admin_user.disable",
    "admin_user.enable", "admin_user.change_role", "admin_user.delete",
    "admin_user.login", "admin_user.permissions_override",
    "rbac.check", "rbac.denied",
    "settings.view", "settings.mutate",
    "agent.rollout.apply", "agent.execution.approve", "agent.execution.reject",
    "crm.reply.send", "crm.export",
    "report.generate", "report.delivery.approve", "report.delivery.send",
    "system.health_check", "system.audit_view",
)


@dataclass(frozen=True)
class AuditEntryResult:
    ok: bool = False
    entry: dict[str, Any] | None = None
    error: str = ""


class AdminAuditLogService:
    """Admin audit log recording with sanitization."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    @staticmethod
    def is_valid_action(action: str) -> bool:
        return action in _VALID_ACTIONS

    @staticmethod
    def is_valid_status(status: str) -> bool:
        return status in _VALID_STATUSES

    @staticmethod
    def get_valid_actions() -> tuple[str, ...]:
        return _VALID_ACTIONS

    @staticmethod
    def get_valid_statuses() -> tuple[str, ...]:
        return _VALID_STATUSES

    @staticmethod
    def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if metadata is None:
            return None
        safe: dict[str, Any] = {}
        for key, val in metadata.items():
            if isinstance(val, str):
                val = _TOKEN_RE.sub("[REDACTED]", val)
                val = _BOT_TOKEN_RE.sub("[REDACTED]", val)
                val = _PHONE_RE.sub("[PHONE_REDACTED]", val)
            safe[key] = val
        return safe

    @staticmethod
    def sanitize_reason(reason: str) -> str:
        if not reason:
            return ""
        reason = _TOKEN_RE.sub("[REDACTED]", reason)
        reason = _BOT_TOKEN_RE.sub("[REDACTED]", reason)
        return reason[:500]

    @staticmethod
    def build_entry(
        actor_admin_id: str = "",
        actor_role: str = "",
        action: str = "",
        target_type: str = "",
        target_id: str = "",
        status: str = "success",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "actor_admin_id": actor_admin_id[:100] if actor_admin_id else "",
            "actor_role": actor_role[:20] if actor_role else "",
            "action": action[:80] if action else "",
            "target_type": target_type[:50] if target_type else "",
            "target_id": target_id[:100] if target_id else "",
            "status": status if status in _VALID_STATUSES else "success",
            "reason": AdminAuditLogService.sanitize_reason(reason),
            "metadata_json": AdminAuditLogService.sanitize_metadata(metadata),
            "created_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def build_denial_entry(
        actor_admin_id: str,
        actor_role: str,
        action: str,
        reason: str,
        target_type: str = "",
        target_id: str = "",
    ) -> dict[str, Any]:
        return AdminAuditLogService.build_entry(
            actor_admin_id=actor_admin_id,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status="denied",
            reason=reason,
        )

    @staticmethod
    def build_failure_entry(
        actor_admin_id: str,
        actor_role: str,
        action: str,
        reason: str,
        target_type: str = "",
        target_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return AdminAuditLogService.build_entry(
            actor_admin_id=actor_admin_id,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status="failed",
            reason=reason,
            metadata=metadata,
        )

    @staticmethod
    def redact_error(error: str) -> str:
        error = _TOKEN_RE.sub("[REDACTED]", error)
        error = _BOT_TOKEN_RE.sub("[REDACTED]", error)
        return error[:500]

    @staticmethod
    def format_for_display(entry: dict[str, Any]) -> dict[str, Any]:
        safe = dict(entry)
        if safe.get("metadata_json"):
            safe["metadata_json"] = AdminAuditLogService.sanitize_metadata(safe["metadata_json"])
        if safe.get("reason"):
            safe["reason"] = AdminAuditLogService.sanitize_reason(safe["reason"])
        return safe
