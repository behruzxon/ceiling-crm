"""
core.services.agent_execution_queue_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Persistent DB-backed execution approval queue.  Manages lifecycle:
proposed → approved/rejected/expired → executed/failed.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.agent_execution_record import (
    AgentExecutionRecordModel,
)
from shared.constants.enums import AgentExecutionStatus
from shared.logging import get_logger

log = get_logger(__name__)

_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)

_FINAL_STATUSES: frozenset[str] = frozenset({
    AgentExecutionStatus.EXECUTED.value,
    AgentExecutionStatus.REJECTED.value,
    AgentExecutionStatus.EXPIRED.value,
    AgentExecutionStatus.FAILED.value,
    AgentExecutionStatus.ROLLED_BACK.value,
})


class AgentExecutionQueueService:
    """DB-backed agent execution queue with approval lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_record(
        self,
        execution_payload: dict[str, Any],
        result: dict[str, Any] | None = None,
        ttl_minutes: int = 30,
    ) -> AgentExecutionRecordModel:
        execution_id = execution_payload.get("execution_id", "")
        if await self._exists(execution_id):
            raise ValueError(f"duplicate_execution_id:{execution_id}")

        now = datetime.now(UTC)
        msg = execution_payload.get("message_text") or ""
        safe_payload = self._redact_payload(dict(execution_payload))

        record = AgentExecutionRecordModel(
            execution_id=execution_id,
            telegram_user_id=execution_payload.get("target_user_id", 0),
            action=execution_payload.get("action", ""),
            mode=execution_payload.get("mode", "log_only"),
            status=AgentExecutionStatus.PROPOSED.value,
            risk_level=execution_payload.get("risk_level", "none"),
            channel=execution_payload.get("channel"),
            payload_json=safe_payload,
            result_json=result,
            message_text_hash=hashlib.sha256(msg.encode()).hexdigest()[:16] if msg else None,
            created_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_execution_id(
        self,
        execution_id: str,
    ) -> AgentExecutionRecordModel | None:
        stmt = sa.select(AgentExecutionRecordModel).where(
            AgentExecutionRecordModel.execution_id == execution_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def approve(
        self,
        execution_id: str,
        admin_id: int,
    ) -> tuple[bool, str]:
        record = await self.get_by_execution_id(execution_id)
        if record is None:
            return False, "not_found"
        if record.status in _FINAL_STATUSES:
            return False, f"already_{record.status}"
        if record.status == AgentExecutionStatus.APPROVED.value:
            return False, "already_approved"
        now = datetime.now(UTC)
        if record.expires_at < now:
            record.status = AgentExecutionStatus.EXPIRED.value
            await self._session.flush()
            return False, "expired"
        record.status = AgentExecutionStatus.APPROVED.value
        record.approved_by = admin_id
        record.approved_at = now
        await self._session.flush()
        return True, "approved"

    async def reject(
        self,
        execution_id: str,
        admin_id: int,
        reason: str = "",
    ) -> tuple[bool, str]:
        record = await self.get_by_execution_id(execution_id)
        if record is None:
            return False, "not_found"
        if record.status in _FINAL_STATUSES:
            return False, f"already_{record.status}"
        record.status = AgentExecutionStatus.REJECTED.value
        record.rejected_by = admin_id
        record.rejected_at = datetime.now(UTC)
        record.rejection_reason = reason[:255] if reason else None
        await self._session.flush()
        return True, "rejected"

    async def mark_executed(
        self,
        execution_id: str,
        result: dict[str, Any] | None = None,
    ) -> bool:
        record = await self.get_by_execution_id(execution_id)
        if record is None:
            return False
        if record.status not in (
            AgentExecutionStatus.APPROVED.value,
            AgentExecutionStatus.PROPOSED.value,
        ):
            return False
        record.status = AgentExecutionStatus.EXECUTED.value
        record.executed_at = datetime.now(UTC)
        if result:
            record.result_json = result
        await self._session.flush()
        return True

    async def mark_failed(
        self,
        execution_id: str,
        error: str,
    ) -> bool:
        record = await self.get_by_execution_id(execution_id)
        if record is None:
            return False
        record.status = AgentExecutionStatus.FAILED.value
        record.failed_at = datetime.now(UTC)
        record.last_error = error[:500]
        await self._session.flush()
        return True

    async def mark_blocked(
        self,
        execution_id: str,
        reason: str,
    ) -> bool:
        record = await self.get_by_execution_id(execution_id)
        if record is None:
            return False
        record.status = AgentExecutionStatus.BLOCKED.value
        record.blocked_reason = reason[:255]
        await self._session.flush()
        return True

    async def expire_pending(
        self,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        if now is None:
            now = datetime.now(UTC)
        stmt = (
            sa.update(AgentExecutionRecordModel)
            .where(
                AgentExecutionRecordModel.status.in_([
                    AgentExecutionStatus.PROPOSED.value,
                    AgentExecutionStatus.APPROVED.value,
                ]),
                AgentExecutionRecordModel.expires_at < now,
            )
            .values(status=AgentExecutionStatus.EXPIRED.value)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def list_pending(self, limit: int = 20) -> list[AgentExecutionRecordModel]:
        stmt = (
            sa.select(AgentExecutionRecordModel)
            .where(AgentExecutionRecordModel.status == AgentExecutionStatus.PROPOSED.value)
            .order_by(AgentExecutionRecordModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_approved_pending(
        self, limit: int = 20,
    ) -> list[AgentExecutionRecordModel]:
        now = datetime.now(UTC)
        stmt = (
            sa.select(AgentExecutionRecordModel)
            .where(
                AgentExecutionRecordModel.status == AgentExecutionStatus.APPROVED.value,
                AgentExecutionRecordModel.executed_at.is_(None),
                AgentExecutionRecordModel.failed_at.is_(None),
                AgentExecutionRecordModel.expires_at > now,
            )
            .order_by(AgentExecutionRecordModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def expire(self, execution_id: str) -> tuple[bool, str]:
        record = await self.get_by_execution_id(execution_id)
        if record is None:
            return False, "not_found"
        if record.status in _FINAL_STATUSES:
            return False, f"already_{record.status}"
        record.status = AgentExecutionStatus.EXPIRED.value
        await self._session.flush()
        return True, "expired"

    @staticmethod
    def sanitize_record_for_api(record: AgentExecutionRecordModel) -> dict[str, Any]:
        payload = dict(record.payload_json or {})
        for key in ("message_text", "admin_alert_text"):
            val = payload.get(key)
            if isinstance(val, str):
                val = _PHONE_RE.sub("[***]", val)
                val = _TOKEN_RE.sub("[REDACTED]", val)
                if len(val) > 100:
                    val = val[:100] + "..."
                payload[key] = val
        return {
            "execution_id": record.execution_id,
            "telegram_user_id": record.telegram_user_id,
            "action": record.action,
            "mode": record.mode,
            "status": record.status,
            "risk_level": record.risk_level,
            "channel": record.channel,
            "payload_preview": payload,
            "approved_by": record.approved_by,
            "rejected_by": record.rejected_by,
            "rejection_reason": record.rejection_reason,
            "blocked_reason": record.blocked_reason,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "executed_at": record.executed_at.isoformat() if record.executed_at else None,
        }

    @staticmethod
    def can_execute(record: AgentExecutionRecordModel) -> bool:
        return record.status == AgentExecutionStatus.APPROVED.value

    @staticmethod
    def build_admin_approval_message(record: AgentExecutionRecordModel) -> str:
        payload = record.payload_json or {}
        msg_preview = payload.get("message_text", "")
        if msg_preview:
            msg_preview = _PHONE_RE.sub("[***]", msg_preview)
            msg_preview = _TOKEN_RE.sub("[REDACTED]", msg_preview)
            msg_preview = msg_preview[:100]

        expires = record.expires_at.strftime("%H:%M") if record.expires_at else "?"
        reason = payload.get("reason", "agent decision")

        return (
            "🧠 Agent action approval\n\n"
            f"👤 User: {record.telegram_user_id}\n"
            f"🎯 Action: {record.action}\n"
            f"📡 Channel: {record.channel or 'n/a'}\n"
            f"⚠️ Risk: {record.risk_level}\n"
            f"⏰ Expires: {expires}\n\n"
            f"📝 Message preview:\n{msg_preview}\n\n"
            f"Reason:\n{reason}"
        )

    @staticmethod
    def build_admin_approval_keyboard(
        record: AgentExecutionRecordModel,
    ) -> list[list[tuple[str, str]]]:
        eid = record.execution_id
        return [[
            ("✅ Approve", f"agentexec:approve:{eid}"),
            ("❌ Reject", f"agentexec:reject:{eid}"),
            ("👁 View", f"agentexec:view:{eid}"),
        ]]

    # ── Private helpers ───────────────────────────────────────────────────

    async def _exists(self, execution_id: str) -> bool:
        if not execution_id:
            return False
        stmt = (
            sa.select(sa.func.count())
            .select_from(AgentExecutionRecordModel)
            .where(AgentExecutionRecordModel.execution_id == execution_id)
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    @staticmethod
    def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
        for key in ("message_text", "admin_alert_text"):
            val = payload.get(key)
            if isinstance(val, str):
                val = _PHONE_RE.sub("[***]", val)
                val = _TOKEN_RE.sub("[REDACTED]", val)
                payload[key] = val
        return payload
