"""
core.services.journey_event_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tracks customer journey events (catalog view, price calc, order start, etc.).

Two entry points:

1. ``JourneyEventService`` — requires an injected session (used in tests / DI).
2. ``emit_journey_event()``  — module-level fire-and-forget helper that opens its
   own session.  Designed to be wrapped in ``asyncio.create_task()`` inside
   handlers so that the user-facing flow is never blocked or broken by a
   tracking failure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.journey_event import JourneyEventModel
from shared.constants.enums import JourneyEventType
from shared.logging import get_logger

log = get_logger(__name__)


class JourneyEventService:
    """CRUD operations on journey events — requires a caller-managed session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        event_type: JourneyEventType | str,
        event_data: dict[str, Any] | None = None,
        source_handler: str | None = None,
    ) -> JourneyEventModel:
        evt = JourneyEventModel(
            user_id=user_id,
            event_type=event_type.value if isinstance(event_type, JourneyEventType) else event_type,
            event_data=event_data or {},
            source_handler=source_handler,
        )
        self._session.add(evt)
        await self._session.flush()
        return evt

    async def get_recent(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[JourneyEventModel]:
        stmt = (
            sa.select(JourneyEventModel)
            .where(JourneyEventModel.user_id == user_id)
            .order_by(JourneyEventModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_last(
        self,
        user_id: int,
        event_type: JourneyEventType | str,
    ) -> JourneyEventModel | None:
        et = event_type.value if isinstance(event_type, JourneyEventType) else event_type
        stmt = (
            sa.select(JourneyEventModel)
            .where(
                JourneyEventModel.user_id == user_id,
                JourneyEventModel.event_type == et,
            )
            .order_by(JourneyEventModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_recent(
        self,
        user_id: int,
        event_type: JourneyEventType | str,
        within_minutes: int = 10,
    ) -> bool:
        et = event_type.value if isinstance(event_type, JourneyEventType) else event_type
        cutoff = datetime.now(UTC) - timedelta(minutes=within_minutes)
        stmt = (
            sa.select(sa.func.count())
            .select_from(JourneyEventModel)
            .where(
                JourneyEventModel.user_id == user_id,
                JourneyEventModel.event_type == et,
                JourneyEventModel.created_at >= cutoff,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0


def _mask_phone(phone: str) -> str:
    """Mask phone for safe storage: +998901234567 → +998**…**67"""
    if len(phone) < 7:
        return "***"
    return phone[:4] + "**…**" + phone[-2:]


async def emit_journey_event(
    user_id: int,
    event_type: JourneyEventType | str,
    event_data: dict[str, Any] | None = None,
    source_handler: str | None = None,
) -> None:
    """Fire-and-forget event emitter with its own DB session.

    Wrap with ``asyncio.create_task(emit_journey_event(...))``.
    Never raises — logs and swallows all exceptions.
    """
    try:
        from infrastructure.database.session import get_session_factory

        safe_data = dict(event_data) if event_data else {}
        if "phone" in safe_data:
            safe_data["phone"] = _mask_phone(str(safe_data["phone"]))

        et_str = event_type.value if isinstance(event_type, JourneyEventType) else event_type

        factory = get_session_factory()
        async with factory() as session:
            svc = JourneyEventService(session)
            await svc.create(
                user_id=user_id,
                event_type=event_type,
                event_data=safe_data,
                source_handler=source_handler,
            )

            # Update agent memory from this event
            try:
                from core.services.agent_memory_service import AgentMemoryService

                mem_svc = AgentMemoryService(session)
                await mem_svc.update_from_event(user_id, et_str, safe_data)
            except Exception:
                log.warning("agent_memory_update_failed", user_id=user_id)

            # Schedule / cancel follow-ups based on event type
            try:
                from core.services.followup_scheduler_service import FollowupSchedulerService
                from shared.config import get_settings

                biz = get_settings().business
                fu_svc = FollowupSchedulerService(session)

                if biz.agent_followups_enabled:
                    if (
                        et_str
                        in {
                            JourneyEventType.OPENED_CATALOG.value,
                            JourneyEventType.VIEWED_CATALOG_ITEM.value,
                        }
                        and biz.agent_catalog_followup_enabled
                    ):
                        delay = biz.agent_catalog_followup_delay_minutes
                        await fu_svc.schedule(user_id, "catalog", et_str, delay_minutes=delay)

                    elif (
                        et_str == JourneyEventType.PRICE_CALCULATED.value
                        and biz.agent_price_followup_enabled
                    ):
                        delay = biz.agent_price_followup_delay_minutes
                        await fu_svc.schedule(user_id, "price", et_str, delay_minutes=delay)

                    elif (
                        et_str == JourneyEventType.ORDER_FORM_STARTED.value
                        and biz.agent_order_followup_enabled
                    ):
                        delay = biz.agent_order_followup_delay_minutes
                        await fu_svc.schedule(
                            user_id, "abandoned_order", et_str, delay_minutes=delay
                        )

                # Cancel runs regardless of feature flag
                if AgentMemoryService.should_cancel_followup_for_event(et_str):
                    await fu_svc.cancel_all_pending(user_id, reason=et_str)
            except Exception:
                log.warning("followup_schedule_failed", user_id=user_id)

            # Evaluate agent decision (log-only, no behavior change)
            try:
                if biz.agent_decision_engine_enabled:
                    from core.services.agent_decision_engine import evaluate as _evaluate

                    mem_svc2 = AgentMemoryService(session)
                    mem_obj = await mem_svc2.get_or_create(user_id)
                    mem_dict = {
                        "full_name": mem_obj.full_name,
                        "phone_masked": mem_obj.phone_masked,
                        "district": mem_obj.district,
                        "interested_designs": mem_obj.interested_designs,
                        "area_m2": mem_obj.area_m2,
                        "ceiling_type": mem_obj.ceiling_type,
                        "estimated_price": mem_obj.estimated_price,
                        "lead_temperature": mem_obj.lead_temperature,
                        "followup_enabled": mem_obj.followup_enabled,
                        "followup_count": mem_obj.followup_count,
                        "last_event_type": mem_obj.last_event_type,
                        "last_event_at": mem_obj.last_event_at,
                        "stop_reason": mem_obj.stop_reason,
                        "objection_type": (mem_obj.memory_data or {}).get("objection_type"),
                    }
                    events = [{"event_type": et_str}]
                    decision = _evaluate(mem_dict, events)
                    log.info(
                        "agent_decision_evaluated",
                        user_id=user_id,
                        state=decision.customer_state,
                        action=decision.action_type,
                        priority=decision.priority_score,
                        confidence=decision.confidence_score,
                    )
            except Exception:
                log.warning("agent_decision_eval_failed", user_id=user_id)

            await session.commit()
    except Exception:
        log.warning("journey_event_emit_failed", user_id=user_id, event_type=str(event_type))
