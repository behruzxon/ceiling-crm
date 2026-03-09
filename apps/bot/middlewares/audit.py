"""
Audit middleware.
Records every significant handler action to the audit_log table.

Every audit record includes ``tenant_id`` for multi-tenant traceability.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from infrastructure.database.models.audit_log import AuditLogModel
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)


class AuditMiddleware(BaseMiddleware):
    """
    Post-handler middleware that writes audit records.
    Handlers can set data["audit_action"] to trigger an audit log entry.

    Expected format:
        data["audit_action"] = {
            "action": "lead.stage_changed",
            "entity_type": "lead",
            "entity_id": 42,
            "old_value": {"stage": "NEW"},
            "new_value": {"stage": "CONTACTED"},
        }

    tenant_id is resolved automatically from handler data (injected by
    AuthMiddleware or TenantContextMiddleware).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        result = await handler(event, data)

        audit_action = data.get("audit_action")
        if audit_action:
            # Fire-and-forget: don't block handler response
            asyncio.create_task(self._write_audit(audit_action, data))

        return result

    @staticmethod
    def _resolve_tenant_id(data: dict[str, Any]) -> int | None:
        """Extract tenant_id from handler data.

        Priority:
        1. data["tenant_id"] (set by TenantContextMiddleware or AuthMiddleware)
        2. data["db_user"].tenant_id (fallback from authenticated user)
        3. audit_action["tenant_id"] (explicit override from handler)
        """
        # Explicit in audit action
        audit = data.get("audit_action", {})
        if "tenant_id" in audit:
            return audit["tenant_id"]

        # From middleware chain
        tid = data.get("tenant_id")
        if tid is not None:
            return tid

        # Fallback: from authenticated user
        db_user = data.get("db_user")
        if db_user is not None:
            return getattr(db_user, "tenant_id", None)

        return None

    async def _write_audit(self, audit: dict[str, Any], data: dict[str, Any]) -> None:
        """Write audit record to DB asynchronously."""
        try:
            db_user = data.get("db_user")
            actor_id = db_user.id if db_user else None
            tenant_id = self._resolve_tenant_id(data)

            if tenant_id is None:
                log.warning(
                    "audit_missing_tenant_id",
                    action=audit.get("action", "unknown"),
                    actor_id=actor_id,
                )
                return

            factory = get_session_factory()
            async with factory() as session:
                record = AuditLogModel(
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    action=audit.get("action", "unknown"),
                    entity_type=audit.get("entity_type", "unknown"),
                    entity_id=audit.get("entity_id", 0),
                    old_value=audit.get("old_value"),
                    new_value=audit.get("new_value"),
                )
                session.add(record)
                await session.commit()

            log.info(
                "audit_recorded",
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=audit.get("action"),
                entity_type=audit.get("entity_type"),
                entity_id=audit.get("entity_id"),
            )
        except Exception:
            log.error(
                "audit_write_failed",
                tenant_id=tenant_id if "tenant_id" in dir() else None,
                action=audit.get("action", "unknown"),
                exc_info=True,
            )
