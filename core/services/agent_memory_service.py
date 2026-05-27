"""
core.services.agent_memory_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Per-user structured memory for the AI sales agent.

Tracks what the bot knows about each customer: catalog interests, pricing
data, lead temperature, follow-up state. Updated automatically when
journey events are emitted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.agent_memory import AgentMemoryModel
from shared.constants.enums import JourneyEventType
from shared.logging import get_logger

log = get_logger(__name__)

_TERMINAL_EVENTS: frozenset[str] = frozenset(
    {
        JourneyEventType.OPERATOR_REQUESTED.value,
        JourneyEventType.DEAL_CLOSED.value,
        JourneyEventType.LOST_LEAD.value,
    }
)

_CANCEL_FOLLOWUP_EVENTS: frozenset[str] = frozenset(
    {
        JourneyEventType.PHONE_SHARED.value,
        JourneyEventType.OPERATOR_REQUESTED.value,
        JourneyEventType.DEAL_CLOSED.value,
        JourneyEventType.LOST_LEAD.value,
    }
)


class AgentMemoryService:
    """CRUD + business logic for per-user agent memory."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self,
        telegram_user_id: int,
        full_name: str | None = None,
    ) -> AgentMemoryModel:
        stmt = sa.select(AgentMemoryModel).where(
            AgentMemoryModel.telegram_user_id == telegram_user_id,
        )
        result = await self._session.execute(stmt)
        mem = result.scalar_one_or_none()
        if mem is not None:
            return mem

        mem = AgentMemoryModel(
            telegram_user_id=telegram_user_id,
            full_name=full_name,
        )
        self._session.add(mem)
        await self._session.flush()
        return mem

    async def update_from_event(
        self,
        telegram_user_id: int,
        event_type: JourneyEventType | str,
        event_data: dict[str, Any] | None = None,
    ) -> AgentMemoryModel:
        et = event_type.value if isinstance(event_type, JourneyEventType) else event_type
        data = event_data or {}
        now = datetime.now(UTC)

        mem = await self.get_or_create(telegram_user_id)
        mem.last_event_type = et
        mem.last_event_at = now
        mem.updated_at = now

        if et == JourneyEventType.OPENED_CATALOG.value:
            pass  # just timestamp update

        elif et == JourneyEventType.VIEWED_CATALOG_ITEM.value:
            design = data.get("design")
            if design:
                designs = list(mem.interested_designs or [])
                if design not in designs:
                    designs.append(design)
                    mem.interested_designs = designs[-10:]  # keep last 10

        elif et == JourneyEventType.PRICE_CALCULATED.value:
            mem.area_m2 = data.get("area_m2") or mem.area_m2
            mem.ceiling_type = data.get("design") or mem.ceiling_type
            mem.estimated_price = data.get("price") or mem.estimated_price
            if mem.lead_temperature == "cold":
                mem.lead_temperature = "warm"

        elif et == JourneyEventType.PHONE_SHARED.value:
            phone = data.get("phone", "")
            if len(phone) >= 7:
                mem.phone_masked = phone[:4] + "**…**" + phone[-2:]
            mem.lead_temperature = "hot"

        elif et == JourneyEventType.CLICKED_ORDER.value:
            if mem.lead_temperature == "cold":
                mem.lead_temperature = "warm"

        elif et == JourneyEventType.ORDER_FORM_STARTED.value:
            if mem.lead_temperature == "cold":
                mem.lead_temperature = "warm"

        elif et in _TERMINAL_EVENTS:
            mem.followup_enabled = False
            mem.stop_reason = et

        await self._session.flush()
        return mem

    async def disable_followup(
        self,
        telegram_user_id: int,
        reason: str,
    ) -> None:
        stmt = (
            sa.update(AgentMemoryModel)
            .where(AgentMemoryModel.telegram_user_id == telegram_user_id)
            .values(
                followup_enabled=False,
                stop_reason=reason,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def mark_followup_sent(self, telegram_user_id: int) -> None:
        now = datetime.now(UTC)
        stmt = (
            sa.update(AgentMemoryModel)
            .where(AgentMemoryModel.telegram_user_id == telegram_user_id)
            .values(
                followup_count=AgentMemoryModel.followup_count + 1,
                last_followup_at=now,
                updated_at=now,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    @staticmethod
    def should_cancel_followup_for_event(event_type: str) -> bool:
        return event_type in _CANCEL_FOLLOWUP_EVENTS
