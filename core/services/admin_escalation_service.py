"""
core.services.admin_escalation_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sends admin alerts when leads ignore follow-ups.

Triggers when followup_count >= threshold AND lead is warm/hot AND
cooldown has elapsed since last escalation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.agent_memory import AgentMemoryModel
from shared.logging import get_logger

log = get_logger(__name__)

_ESCALATABLE_TEMPS: frozenset[str] = frozenset({"hot", "warm"})


class AdminEscalationService:
    """Check and send admin escalation alerts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def should_escalate(
        self,
        memory: AgentMemoryModel,
        threshold: int,
        cooldown_minutes: int,
    ) -> tuple[bool, str]:
        if not memory.followup_enabled:
            return False, "followup_disabled"
        if memory.lead_temperature not in _ESCALATABLE_TEMPS:
            return False, "cold_lead"
        if memory.followup_count < threshold:
            return False, "below_threshold"
        if memory.last_admin_escalation_at:
            elapsed = (datetime.now(UTC) - memory.last_admin_escalation_at).total_seconds()
            if elapsed < cooldown_minutes * 60:
                return False, "cooldown"
        return True, "ok"

    async def get_escalation_candidates(
        self,
        threshold: int,
        cooldown_minutes: int,
        limit: int = 20,
    ) -> list[AgentMemoryModel]:
        cutoff = datetime.now(UTC) - timedelta(minutes=cooldown_minutes)
        stmt = (
            sa.select(AgentMemoryModel)
            .where(
                AgentMemoryModel.followup_enabled.is_(True),
                AgentMemoryModel.lead_temperature.in_(list(_ESCALATABLE_TEMPS)),
                AgentMemoryModel.followup_count >= threshold,
                sa.or_(
                    AgentMemoryModel.last_admin_escalation_at.is_(None),
                    AgentMemoryModel.last_admin_escalation_at < cutoff,
                ),
            )
            .order_by(AgentMemoryModel.last_followup_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_escalated(
        self,
        telegram_user_id: int,
        reason: str,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            sa.update(AgentMemoryModel)
            .where(AgentMemoryModel.telegram_user_id == telegram_user_id)
            .values(
                admin_escalation_count=AgentMemoryModel.admin_escalation_count + 1,
                last_admin_escalation_at=now,
                admin_escalation_reason=reason[:100],
                updated_at=now,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    @staticmethod
    def build_admin_alert(memory: AgentMemoryModel) -> str:
        temp_emoji = {"hot": "🔥", "warm": "🟡", "cold": "❄️"}.get(
            memory.lead_temperature,
            "❓",
        )
        name = memory.full_name or "Noma'lum"
        phone = memory.phone_masked or "—"
        district = memory.district or "noma'lum"
        area = f"{memory.area_m2:.1f} m²" if memory.area_m2 else "noma'lum"
        ceiling = memory.ceiling_type or "noma'lum"
        price = f"{memory.estimated_price:,} UZS" if memory.estimated_price else "noma'lum"
        last_event = memory.last_event_type or "—"
        fu_count = memory.followup_count
        last_fu = (
            memory.last_followup_at.strftime("%d.%m %H:%M") if memory.last_followup_at else "—"
        )

        return (
            f"{temp_emoji} <b>LEAD JIM QOLDI</b>\n\n"
            f"👤 Mijoz: {name}\n"
            f"📞 Telefon: {phone}\n"
            f"📍 Hudud: {district}\n"
            f"📐 Maydon: {area}\n"
            f"🏠 Potolok: {ceiling}\n"
            f"💰 Narx: {price}\n"
            f"🌡 Holat: {memory.lead_temperature}\n\n"
            f"🧠 Oxirgi harakat: {last_event}\n"
            f"⏰ Oxirgi follow-up: {last_fu}\n"
            f"📨 Follow-up soni: {fu_count}\n\n"
            "🎯 <b>Tavsiya:</b>\n"
            "Mijozga hozir yozing yoki qo'ng'iroq qiling."
        )

    @staticmethod
    def build_admin_keyboard(
        telegram_user_id: int,
    ) -> list[list[tuple[str, str]]]:
        return [
            [
                ("💬 Yozish", f"agentesc:write:{telegram_user_id}"),
                ("✅ Bog'landik", f"agentesc:contacted:{telegram_user_id}"),
            ],
            [
                ("❌ Kerak emas", f"agentesc:stop:{telegram_user_id}"),
            ],
        ]
