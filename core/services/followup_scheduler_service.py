"""
core.services.followup_scheduler_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
10-minute follow-up engine.

Schedules, validates, and sends deterministic follow-up messages to
customers who viewed the catalog, calculated a price, or started an
order but went silent.

Anti-spam: 5-layer protection
  1. Per-type Redis dedup (NX key)
  2. Min-gap Redis cooldown (10 min)
  3. Daily counter (max 3 / 24h) — Redis primary, DB fallback
  4. Lifetime cap (max 5 total) — DB column
  5. followup_enabled flag — DB column

Stale check: before sending, verifies no superseding event occurred
after the follow-up was scheduled.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.agent_memory import AgentMemoryModel
from infrastructure.database.models.journey_event import JourneyEventModel
from infrastructure.database.models.scheduled_followup import ScheduledFollowupModel
from shared.constants.enums import JourneyEventType
from shared.logging import get_logger

log = get_logger(__name__)

_MAX_DAILY_FOLLOWUPS = 3
_MAX_TOTAL_FOLLOWUPS = 5
_MIN_GAP_SECONDS = 600  # 10 min

_STOP_WORDS: frozenset[str] = frozenset({
    "kerak emas", "kerakmas", "hozir emas", "stop", "bekor",
    "qiziqmayman", "yozmang", "не надо", "стоп", "отмена",
    "yoq kerak emas", "rahmat kerak emas",
})

_SUPERSEDING_EVENTS: dict[str, frozenset[str]] = {
    "catalog": frozenset({
        JourneyEventType.PRICE_CALCULATED.value,
        JourneyEventType.CLICKED_ORDER.value,
        JourneyEventType.ORDER_FORM_STARTED.value,
        JourneyEventType.PHONE_SHARED.value,
        JourneyEventType.OPERATOR_REQUESTED.value,
        JourneyEventType.DEAL_CLOSED.value,
        JourneyEventType.LOST_LEAD.value,
    }),
    "price": frozenset({
        JourneyEventType.CLICKED_ORDER.value,
        JourneyEventType.ORDER_FORM_STARTED.value,
        JourneyEventType.PHONE_SHARED.value,
        JourneyEventType.OPERATOR_REQUESTED.value,
        JourneyEventType.DEAL_CLOSED.value,
        JourneyEventType.LOST_LEAD.value,
    }),
    "abandoned_order": frozenset({
        JourneyEventType.PHONE_SHARED.value,
        JourneyEventType.LOCATION_SHARED.value,
        JourneyEventType.OPERATOR_REQUESTED.value,
        JourneyEventType.DEAL_CLOSED.value,
        JourneyEventType.LOST_LEAD.value,
    }),
}

_FOLLOWUP_MESSAGES: dict[str, str] = {
    "catalog": (
        "Salom 😊 Katalogdagi qaysi model sizga ko'proq yoqdi?\n"
        "Xonangiz kvadratini yozsangiz, taxminiy narxni hisoblab beraman."
    ),
    "price": (
        "Hisob-kitob bo’yicha savol bormi? 😊\n"
        "Xohlasangiz operatorimiz aniq o’lchov va chegirma bo’yicha yordam beradi."
    ),
    "abandoned_order": (
        "Buyurtmani davom ettiramizmi? 😊\n"
        "Telefon raqamingizni yuborsangiz, operatorimiz siz bilan bog’lanadi."
    ),
}

_FOLLOWUP_BUTTONS: dict[str, list[tuple[str, str]]] = {
    "catalog": [
        ("💰 Narx hisoblash", "agentfu:price"),
        ("🛒 Zakaz berish", "agentfu:order"),
        ("👨‍💼 Operator", "agentfu:operator"),
    ],
    "price": [
        ("🛒 Zakaz berish", "agentfu:order"),
        ("👨‍💼 Operator", "agentfu:operator"),
        ("❌ Kerak emas", "agentfu:stop"),
    ],
    "abandoned_order": [
        ("✅ Davom etish", "agentfu:resume"),
        ("👨‍💼 Operator", "agentfu:operator"),
        ("❌ Kerak emas", "agentfu:stop"),
    ],
}


class FollowupSchedulerService:
    """Schedule and process 10-minute follow-up messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def schedule(
        self,
        telegram_user_id: int,
        followup_type: str,
        trigger_event_type: str,
        delay_minutes: int = 10,
    ) -> ScheduledFollowupModel | None:
        existing = await self._has_pending(telegram_user_id, followup_type)
        if existing:
            return None

        scheduled_at = datetime.now(UTC) + timedelta(minutes=delay_minutes)
        fu = ScheduledFollowupModel(
            telegram_user_id=telegram_user_id,
            followup_type=followup_type,
            trigger_event_type=trigger_event_type,
            scheduled_at=scheduled_at,
            status="pending",
        )
        self._session.add(fu)
        await self._session.flush()
        return fu

    async def cancel_all_pending(
        self,
        telegram_user_id: int,
        reason: str = "user_action",
    ) -> int:
        now = datetime.now(UTC)
        stmt = (
            sa.update(ScheduledFollowupModel)
            .where(
                ScheduledFollowupModel.telegram_user_id == telegram_user_id,
                ScheduledFollowupModel.status == "pending",
            )
            .values(status="cancelled", cancelled_at=now, last_error=reason, updated_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def get_due(self, now: datetime, limit: int = 20) -> list[ScheduledFollowupModel]:
        stmt = (
            sa.select(ScheduledFollowupModel)
            .where(
                ScheduledFollowupModel.status == "pending",
                ScheduledFollowupModel.scheduled_at <= now,
            )
            .order_by(ScheduledFollowupModel.scheduled_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, followup_id: int, message_text: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            sa.update(ScheduledFollowupModel)
            .where(ScheduledFollowupModel.id == followup_id)
            .values(
                status="sent",
                sent_at=now,
                message_text=message_text,
                attempt_count=ScheduledFollowupModel.attempt_count + 1,
                updated_at=now,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def mark_failed(self, followup_id: int, error: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            sa.update(ScheduledFollowupModel)
            .where(ScheduledFollowupModel.id == followup_id)
            .values(
                status="failed",
                last_error=error[:500],
                attempt_count=ScheduledFollowupModel.attempt_count + 1,
                updated_at=now,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def mark_skipped(self, followup_id: int, reason: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            sa.update(ScheduledFollowupModel)
            .where(ScheduledFollowupModel.id == followup_id)
            .values(status="skipped", last_error=reason, updated_at=now)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def reschedule(self, followup_id: int, new_time: datetime) -> None:
        stmt = (
            sa.update(ScheduledFollowupModel)
            .where(ScheduledFollowupModel.id == followup_id)
            .values(scheduled_at=new_time, updated_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def should_send(
        self,
        followup: ScheduledFollowupModel,
        memory: AgentMemoryModel | None,
    ) -> tuple[bool, str]:
        if memory is None:
            return False, "no_memory"
        if not memory.followup_enabled:
            return False, f"disabled:{memory.stop_reason}"
        if memory.followup_count >= _MAX_TOTAL_FOLLOWUPS:
            return False, "lifetime_cap"

        # DB-based daily limit fallback (in case Redis unavailable)
        daily_count = await self._count_sent_today(followup.telegram_user_id)
        if daily_count >= _MAX_DAILY_FOLLOWUPS:
            return False, "daily_cap"

        # DB-based gap check fallback
        if memory.last_followup_at:
            gap = (datetime.now(UTC) - memory.last_followup_at).total_seconds()
            if gap < _MIN_GAP_SECONDS:
                return False, "min_gap"

        # Stale check: superseding event after schedule time
        is_stale = await self._is_stale(followup)
        if is_stale:
            return False, "stale"

        # Conversation policy check (only when enabled + enforced)
        try:
            from shared.config import get_settings
            biz = get_settings().business
            if biz.agent_conversation_policy_enabled and not biz.agent_conversation_policy_log_only:
                md = memory.memory_data or {}
                last_policy = md.get("last_conversation_policy")
                if isinstance(last_policy, dict):
                    pa = last_policy.get("policy_action", "")
                    if pa in ("no_action", "disable_agent"):
                        return False, f"policy:{pa}"
        except Exception:
            pass

        return True, "ok"

    async def _is_stale(self, followup: ScheduledFollowupModel) -> bool:
        superseding = _SUPERSEDING_EVENTS.get(followup.followup_type)
        if not superseding:
            return False

        stmt = (
            sa.select(sa.func.count())
            .select_from(JourneyEventModel)
            .where(
                JourneyEventModel.user_id == followup.telegram_user_id,
                JourneyEventModel.event_type.in_(superseding),
                JourneyEventModel.created_at > followup.created_at,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def _has_pending(self, telegram_user_id: int, followup_type: str) -> bool:
        stmt = (
            sa.select(sa.func.count())
            .select_from(ScheduledFollowupModel)
            .where(
                ScheduledFollowupModel.telegram_user_id == telegram_user_id,
                ScheduledFollowupModel.followup_type == followup_type,
                ScheduledFollowupModel.status == "pending",
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def _count_sent_today(self, telegram_user_id: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stmt = (
            sa.select(sa.func.count())
            .select_from(ScheduledFollowupModel)
            .where(
                ScheduledFollowupModel.telegram_user_id == telegram_user_id,
                ScheduledFollowupModel.status == "sent",
                ScheduledFollowupModel.sent_at >= cutoff,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    def is_stop_signal(text: str) -> bool:
        normalized = text.strip().lower()
        return normalized in _STOP_WORDS

    @staticmethod
    def build_message(followup_type: str) -> tuple[str, list[tuple[str, str]]]:
        text = _FOLLOWUP_MESSAGES.get(followup_type, "")
        buttons = _FOLLOWUP_BUTTONS.get(followup_type, [])
        return text, buttons

    @staticmethod
    async def build_message_ai(
        followup_type: str,
        memory_data: dict[str, object] | None = None,
    ) -> tuple[str, list[tuple[str, str]]]:
        """AI-personalized message with deterministic fallback. Buttons unchanged."""
        fallback_text = _FOLLOWUP_MESSAGES.get(followup_type, "")
        buttons = list(_FOLLOWUP_BUTTONS.get(followup_type, []))

        if not memory_data:
            return fallback_text, buttons

        # Inject dynamic offer context if available (does not change buttons)
        md = dict(memory_data)
        try:
            from shared.config import get_settings
            if get_settings().business.agent_dynamic_offer_enabled:
                from core.services.dynamic_offer_service import DynamicOfferService
                offer = DynamicOfferService.choose_offer(
                    memory=md,
                    lead_signal=None,
                    recent_events=[],
                )
                if offer.offer_type != "no_offer":
                    md = DynamicOfferService.store_offer_to_memory(md, offer)
        except Exception:
            pass

        try:
            from core.services.ai_message_composer_service import compose_followup
            text = await compose_followup(followup_type, md, fallback_text)
        except Exception:
            text = fallback_text

        return text, buttons
