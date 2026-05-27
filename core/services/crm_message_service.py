"""
core.services.crm_message_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CRM message recording and timeline.
"""
from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.crm_message import CRMMessageModel
from shared.logging import get_logger

log = get_logger(__name__)
_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


class CRMMessageService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_inbound(
        self, contact_id: int, telegram_user_id: int,
        text: str, message_type: str = "text", payload: dict | None = None,
    ) -> CRMMessageModel:
        redacted = self.redact_text(text) if text else None
        sensitive = redacted != text if text and redacted else False
        msg = CRMMessageModel(
            contact_id=contact_id, telegram_user_id=telegram_user_id,
            direction="inbound", sender_type="user", text=text,
            message_type=message_type, payload_json=payload,
            redacted_text=redacted, is_sensitive=sensitive,
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def record_outbound(
        self, contact_id: int, text: str,
        sender_type: str = "bot", payload: dict | None = None,
    ) -> CRMMessageModel:
        msg = CRMMessageModel(
            contact_id=contact_id, direction="outbound",
            sender_type=sender_type, text=text, payload_json=payload,
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def record_agent_trace(
        self, contact_id: int, trace_data: dict[str, Any],
    ) -> CRMMessageModel:
        msg = CRMMessageModel(
            contact_id=contact_id, direction="agent_trace",
            sender_type="agent", message_type="system",
            payload_json=trace_data,
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def list_messages(
        self, contact_id: int, limit: int = 100,
    ) -> list[CRMMessageModel]:
        stmt = (
            sa.select(CRMMessageModel)
            .where(CRMMessageModel.contact_id == contact_id)
            .order_by(CRMMessageModel.created_at.desc())
            .limit(min(limit, 200))
        )
        r = await self._session.execute(stmt)
        return list(r.scalars().all())

    @staticmethod
    def redact_text(text: str) -> str:
        text = _PHONE_RE.sub("[***]", text)
        text = _TOKEN_RE.sub("[REDACTED]", text)
        return text
