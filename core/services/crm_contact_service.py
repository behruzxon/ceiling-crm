"""
core.services.crm_contact_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CRM contact CRUD + lead management.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.crm_contact import CRMContactModel
from infrastructure.database.models.crm_message import CRMContactNoteModel, CRMContactTagModel
from shared.logging import get_logger

log = get_logger(__name__)

_VALID_STATUSES = frozenset({
    "new", "active", "browsing", "price_interested", "hot",
    "operator_needed", "order_started", "won", "lost", "stopped",
})
_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


class CRMContactService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_contact(
        self, *, telegram_user_id: int, chat_id: int | None = None,
        username: str | None = None, first_name: str | None = None,
        last_name: str | None = None, language_code: str | None = None,
        source: str = "telegram_bot",
    ) -> CRMContactModel:
        stmt = sa.select(CRMContactModel).where(
            CRMContactModel.telegram_user_id == telegram_user_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(UTC)
        if existing:
            if username: existing.username = username
            if first_name: existing.first_name = first_name
            if last_name: existing.last_name = last_name
            if language_code: existing.language_code = language_code
            if chat_id: existing.telegram_chat_id = chat_id
            existing.last_seen_at = now
            existing.updated_at = now
            await self._session.flush()
            return existing
        contact = CRMContactModel(
            telegram_user_id=telegram_user_id, telegram_chat_id=chat_id,
            username=username, first_name=first_name, last_name=last_name,
            language_code=language_code, source=source, last_seen_at=now,
        )
        self._session.add(contact)
        await self._session.flush()
        return contact

    async def get_contact(self, contact_id: int) -> CRMContactModel | None:
        return (await self._session.execute(
            sa.select(CRMContactModel).where(CRMContactModel.id == contact_id),
        )).scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_user_id: int) -> CRMContactModel | None:
        return (await self._session.execute(
            sa.select(CRMContactModel).where(
                CRMContactModel.telegram_user_id == telegram_user_id,
            ),
        )).scalar_one_or_none()

    async def update_lead_status(self, contact_id: int, status: str) -> bool:
        if status not in _VALID_STATUSES:
            return False
        stmt = sa.update(CRMContactModel).where(
            CRMContactModel.id == contact_id,
        ).values(lead_status=status, updated_at=datetime.now(UTC))
        await self._session.execute(stmt)
        await self._session.flush()
        return True

    async def update_score(
        self, contact_id: int, score: int, temperature: str | None = None,
    ) -> None:
        vals: dict[str, Any] = {"lead_score": score, "updated_at": datetime.now(UTC)}
        if temperature:
            vals["temperature"] = temperature
        await self._session.execute(
            sa.update(CRMContactModel).where(CRMContactModel.id == contact_id).values(**vals),
        )
        await self._session.flush()

    async def add_note(
        self, contact_id: int, text: str, created_by: str | None = None,
    ) -> CRMContactNoteModel:
        note = CRMContactNoteModel(
            contact_id=contact_id, note_text=text[:2000], created_by=created_by,
        )
        self._session.add(note)
        await self._session.flush()
        return note

    async def add_tag(self, contact_id: int, tag: str) -> bool:
        tag = tag.strip()[:30]
        try:
            self._session.add(CRMContactTagModel(contact_id=contact_id, tag=tag))
            await self._session.flush()
            return True
        except Exception:
            return False

    async def remove_tag(self, contact_id: int, tag: str) -> bool:
        stmt = sa.delete(CRMContactTagModel).where(
            CRMContactTagModel.contact_id == contact_id,
            CRMContactTagModel.tag == tag,
        )
        r = await self._session.execute(stmt)
        await self._session.flush()
        return (r.rowcount or 0) > 0

    @staticmethod
    def is_valid_status(status: str) -> bool:
        return status in _VALID_STATUSES

    @staticmethod
    def redact_text(text: str) -> str:
        text = _PHONE_RE.sub("[***]", text)
        text = _TOKEN_RE.sub("[REDACTED]", text)
        return text
