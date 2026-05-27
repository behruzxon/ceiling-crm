"""
core.services.followup_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Processes overdue lead follow-up reminders.

The scheduler calls ``process_due_followups()`` every 60 seconds.
For each lead whose ``next_follow_up_at`` is in the past the service:
  1. Asks the follow-up brain whether and how to follow up.
  2. Sends a context-aware reminder to the admin with quick-action buttons.
  3. Increments ``follow_up_count``.
  4. Schedules the next reminder using brain-computed delay.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)

# Safety cap: stop following up after this many reminders to prevent spam.
# Kept here as a hard backstop — the brain also checks this, but this is the
# authoritative guard that cannot be overridden.
_MAX_FOLLOWUP_COUNT = 5


class FollowupService:
    """Send admin reminders for overdue leads and reschedule them."""

    def __init__(self, bot_token: str, admin_user_id: int | None) -> None:
        self._bot_token = bot_token
        self._admin_user_id = admin_user_id

    async def process_due_followups(self) -> int:
        """Send reminders for all overdue leads. Returns the count of processed leads."""
        if not self._admin_user_id:
            return 0

        now = datetime.now(UTC)
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
                        # Safety cap: stop reminders after _MAX_FOLLOWUP_COUNT
                        if (lead.follow_up_count or 0) >= _MAX_FOLLOWUP_COUNT:
                            await repo.update_ai_scoring(lead.id, next_follow_up_at=None)
                            log.info(
                                "followup_cap_reached", lead_id=lead.id, count=lead.follow_up_count
                            )
                            continue

                        # ── Ask the follow-up brain ─────────────────────
                        fu_decision = self._compute_brain_decision(lead)

                        # Brain says skip → clear schedule
                        if not fu_decision.should_follow_up:
                            await repo.update_ai_scoring(lead.id, next_follow_up_at=None)
                            log.info(
                                "followup_brain_skip",
                                lead_id=lead.id,
                                reason=fu_decision.skip_reason,
                            )
                            continue

                        # ── Build admin reminder card ───────────────────
                        conf_str = (
                            f"{lead.closing_confidence:.0%}"
                            if lead.closing_confidence is not None
                            else "\u2014"
                        )

                        # Deal probability line
                        prob_line = ""
                        try:
                            from shared.utils.deal_probability import evaluate_deal_probability

                            _sv = None
                            try:
                                from core.services.signal_vector_service import build_signal_vector

                                _sv = build_signal_vector(
                                    lead_score=lead.score or 0,
                                    closing_confidence=lead.closing_confidence,
                                    phone_captured=bool(lead.phone),
                                    has_area=lead.room_area is not None,
                                    area_m2=float(lead.room_area) if lead.room_area else None,
                                    has_district=bool(lead.district),
                                    follow_up_count=lead.follow_up_count or 0,
                                    lead_temperature=lead.lead_temperature,
                                )
                            except Exception:
                                pass
                            _dp = (
                                evaluate_deal_probability(signal_vector=_sv)
                                if _sv
                                else evaluate_deal_probability(
                                    score=lead.score or 0,
                                    closing_confidence=lead.closing_confidence,
                                    phone_captured=bool(lead.phone),
                                    has_area=lead.room_area is not None,
                                    area_m2=lead.room_area,
                                    has_district=bool(lead.district),
                                    follow_up_count=lead.follow_up_count or 0,
                                )
                            )
                            prob_line = f"\n\U0001f4ca Ehtimol: {_dp.deal_probability_percent}%"
                            if _dp.expected_deal_value is not None:
                                prob_line += f" | {_dp.expected_deal_value:,} UZS"
                        except Exception:
                            pass

                        # Brain decision line
                        from core.services.followup_brain_service import FU_TYPE_LABELS

                        fu_label = FU_TYPE_LABELS.get(
                            fu_decision.follow_up_type,
                            fu_decision.follow_up_type,
                        )
                        delay_str = self._format_delay(fu_decision.follow_up_delay_minutes)
                        brain_line = f"\n\U0001f9e0 FU: {fu_label} | {delay_str}"

                        text = (
                            f"\u23f0 <b>Follow-up eslatmasi</b>\n\n"
                            f"\U0001f4cb Lid #{lead.id} \u2014 {lead.name}\n"
                            f"\U0001f4f1 {lead.phone}\n"
                            f"\U0001f4cd {lead.district}\n"
                            f"\U0001f321 Holat: {lead.lead_temperature or chr(0x2014)}\n"
                            f"\U0001f4a1 Ishonch: {conf_str}\n"
                            f"\U0001f501 Follow-up #{(lead.follow_up_count or 0) + 1}"
                            f"{prob_line}{brain_line}\n\n"
                            f"/lead_{lead.id}"
                        )
                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="\U0001f4cc Kanban'da ochish",
                                        callback_data=f"kanban:lead:{lead.id}:new",
                                    ),
                                ],
                                [
                                    InlineKeyboardButton(
                                        text="\u2705 Bog'landim",
                                        callback_data=f"lead:{lead.id}:status:contacted",
                                    ),
                                    InlineKeyboardButton(
                                        text="\u274c Yo'qotildi",
                                        callback_data=f"lead:{lead.id}:status:lost",
                                    ),
                                ],
                            ]
                        )
                        from shared.utils.telegram_send import safe_send_message

                        await safe_send_message(
                            bot, self._admin_user_id, text, reply_markup=keyboard
                        )

                        # ── Reschedule using brain delay ────────────────
                        delay_minutes = fu_decision.follow_up_delay_minutes or 360
                        next_fu = now + timedelta(minutes=delay_minutes)

                        # Defer to business hours if next_fu falls off-hours
                        try:
                            from shared.utils.business_hours import (
                                defer_to_business_hours,
                                is_off_hours,
                            )

                            if is_off_hours(next_fu):
                                next_fu = defer_to_business_hours(next_fu)
                        except Exception:
                            pass  # safety: keep original schedule
                        await repo.update_ai_scoring(
                            lead.id,
                            next_follow_up_at=next_fu,
                            increment_followup_count=True,
                        )

                        # Log tactic outcome for outcome-based learning
                        import asyncio as _aio

                        from core.services.tactic_outcome_logger import log_tactic_outcome

                        _aio.create_task(
                            log_tactic_outcome(
                                event_type="followup",
                                tactic_name=fu_decision.follow_up_type or "price_reminder",
                                user_id=lead.user_id,
                                lead_id=lead.id,
                                lead_score_at_time=lead.score or 0,
                                lead_temperature_at_time=lead.lead_temperature,
                            )
                        )

                        processed += 1
                    except Exception:
                        log.exception("followup_send_failed", lead_id=lead.id)

                await session.commit()
            finally:
                await bot.session.close()

        log.info("followups_processed", count=processed)
        return processed

    @staticmethod
    def _compute_brain_decision(lead: object) -> FollowUpDecision:  # noqa: F821
        """Run the follow-up brain on a lead domain object. Never raises."""
        from core.services.followup_brain_service import decide_follow_up

        try:
            return decide_follow_up(
                score=lead.score or 0,  # type: ignore[union-attr]
                deal_probability_percent=None,  # computed separately for card
                buyer_type=None,  # not stored on lead — brain uses other signals
                decision_stage=None,  # not stored on lead
                engagement_trend=None,  # not stored on lead
                last_objection=None,  # not stored on lead
                phone_captured=bool(lead.phone),  # type: ignore[union-attr]
                has_area=lead.room_area is not None,  # type: ignore[union-attr]
                has_district=bool(lead.district),  # type: ignore[union-attr]
                has_design=False,
                closing_attempted=False,
                negotiation_tactic=None,
                negotiation_escalated=False,
                follow_up_count=lead.follow_up_count or 0,  # type: ignore[union-attr]
                closing_confidence=lead.closing_confidence,  # type: ignore[union-attr]
                lead_temperature=lead.lead_temperature,  # type: ignore[union-attr]
            )
        except Exception:
            log.warning("followup_brain_error", lead_id=lead.id)  # type: ignore[union-attr]
            # Fallback: always follow up with default
            from core.services.followup_brain_service import FollowUpDecision

            return FollowUpDecision(
                should_follow_up=True,
                follow_up_delay_minutes=360,
                follow_up_type="price_reminder",
                follow_up_message="",
                follow_up_reason="Fallback — brain error",
                skip_reason=None,
            )

    @staticmethod
    def _format_delay(minutes: int | None) -> str:
        """Format delay minutes as human-readable string."""
        if minutes is None:
            return "\u2014"
        if minutes < 60:
            return f"{minutes} daqiqa"
        hours = minutes / 60
        if hours < 24:
            return f"{hours:.0f} soat"
        days = hours / 24
        return f"{days:.1f} kun"
