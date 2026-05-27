"""
Audit middleware.
Records every significant handler action to the audit_log table.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

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

    async def _write_audit(self, audit: dict[str, Any], data: dict[str, Any]) -> None:
        """Write audit record to DB asynchronously."""
        try:
            db_user = data.get("db_user")
            actor_id = db_user.id if db_user else None

            factory = get_session_factory()
            async with factory() as session:
                record = AuditLogModel(
                    actor_id=actor_id,
                    action=audit.get("action", "unknown"),
                    entity_type=audit.get("entity_type", "unknown"),
                    entity_id=audit.get("entity_id", 0),
                    old_value=audit.get("old_value"),
                    new_value=audit.get("new_value"),
                )
                session.add(record)
                await session.commit()
        except Exception:
            log.error("audit_write_failed", exc_info=True)
