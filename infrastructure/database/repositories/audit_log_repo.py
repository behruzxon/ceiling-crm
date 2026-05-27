"""Simple write-only repository for audit_logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.audit_log import AuditLogModel
from shared.logging import get_logger

log = get_logger(__name__)


class PostgresAuditLogRepository:
    """Append-only repository for audit_logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        actor_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
    ) -> None:
        """Append one audit log row.

        Never raises — logs and swallows errors so a logging failure never
        aborts the primary business operation.
        """
        try:
            self._session.add(
                AuditLogModel(
                    actor_id=actor_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    old_value=old_value,
                    new_value=new_value,
                )
            )
        except Exception:
            log.exception(
                "audit_log_insert_error",
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
            )
