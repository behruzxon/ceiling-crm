"""
core.services.followup_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Processes overdue lead follow-up reminders.

The scheduler calls ``process_due_followups()`` every 60 seconds.
For each lead whose ``next_follow_up_at`` is in the past the service:
  1. Sends a reminder message to the admin with quick-action buttons.
  2. Increments ``follow_up_count``.
  3. Schedules the next reminder based on ``_RESCHEDULE_BY_TEMP`` (hot=1h, warm=6h, cold=24h).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)

# Hours until next reminder, keyed by lead_temperature.
# Mirrors the initial scheduling logic in shared/utils/lead_scoring.py:
#   hot → 20 min (initial), then 1 h cadence
#   warm → 3 h (initial), then 6 h cadence
#   cold → 24 h both
_RESCHEDULE_BY_TEMP: dict[str | None, int] = {
    "hot": 1,
    "warm": 6,
    "cold": 24,
}


class FollowupService:
    """Send admin reminders for overdue leads and reschedule them."""

    def __init__(self, bot_token: str, admin_user_id: int | None) -> None:
        self._bot_token = bot_token
        self._admin_user_id = admin_user_id

    async def process_due_followups(self) -> int:
        """Send reminders for all overdue leads. Returns the count of processed leads."""
        if not self._admin_user_id:
            return 0

        now = datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            leads = await repo.get_due_followups(now)
            if not leads:
                return 0

            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            bot = Bot(
                token=self._bot_token,
                default=DefaultBotProperties(parse_mode="HTML"),
            )
            processed = 0
            try:
                for lead in leads:
                    try:
                        conf_str = (
                            f"{lead.closing_confidence:.0%}"
                            if lead.closing_confidence is not None
                            else "—"
                        )
                        text = (
                            f"⏰ <b>Follow-up eslatmasi</b>\n\n"
                            f"📋 Lid #{lead.id} — {lead.name}\n"
                            f"📱 {lead.phone}\n"
                            f"📍 {lead.district}\n"
                            f"🌡 Holat: {lead.lead_temperature or '—'}\n"
                            f"💡 Ishonch: {conf_str}\n"
                            f"🔁 Follow-up #{lead.follow_up_count + 1}\n\n"
                            f"/lead_{lead.id}"
                        )
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="📌 Kanban'da ochish",
                                    callback_data=f"kanban:lead:{lead.id}:new",
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    text="✅ Bog'landim",
                                    callback_data=f"lead:{lead.id}:status:contacted",
                                ),
                                InlineKeyboardButton(
                                    text="❌ Yo'qotildi",
                                    callback_data=f"lead:{lead.id}:status:lost",
                                ),
                            ],
                        ])
                        await bot.send_message(
                            self._admin_user_id, text, reply_markup=keyboard
                        )
                        reschedule_h = _RESCHEDULE_BY_TEMP.get(lead.lead_temperature, 6)
                        next_fu = now + timedelta(hours=reschedule_h)
                        await repo.update_ai_scoring(
                            lead.id,
                            next_follow_up_at=next_fu,
                            increment_followup_count=True,
                        )
                        processed += 1
                    except Exception:
                        log.exception("followup_send_failed", lead_id=lead.id)

                await session.commit()
            finally:
                await bot.session.close()

        log.info("followups_processed", count=processed)
        return processed
