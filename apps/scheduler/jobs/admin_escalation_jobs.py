"""APScheduler job: send admin alerts for leads ignoring follow-ups."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_admin_escalation_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        process_admin_escalations,
        trigger="interval",
        seconds=120,
        id="process_admin_escalations",
        replace_existing=True,
    )


async def process_admin_escalations() -> None:
    """Find leads that ignored follow-ups and alert admins."""
    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        from core.services.admin_escalation_service import AdminEscalationService
        from infrastructure.database.session import get_session_factory
        from shared.config import get_settings
        from shared.utils.business_hours import is_off_hours

        settings = get_settings()
        biz = settings.business
        if not biz.agent_followups_enabled or not biz.agent_admin_escalation_enabled:
            return
        if is_off_hours():
            return

        admin_group_id = settings.bot.admin_group_id
        if not admin_group_id:
            return

        bot_token = settings.bot.token.get_secret_value()
        threshold = biz.agent_admin_escalation_after_followups
        cooldown = biz.agent_admin_escalation_cooldown_minutes

        factory = get_session_factory()
        async with factory() as session:
            esc_svc = AdminEscalationService(session)
            candidates = await esc_svc.get_escalation_candidates(
                threshold=threshold, cooldown_minutes=cooldown, limit=20,
            )
            if not candidates:
                return

            bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode="HTML"))
            sent = 0
            try:
                for mem in candidates:
                    try:
                        ok, reason = esc_svc.should_escalate(mem, threshold, cooldown)
                        if not ok:
                            continue

                        text = AdminEscalationService.build_admin_alert(mem)
                        kb_data = AdminEscalationService.build_admin_keyboard(
                            mem.telegram_user_id,
                        )
                        rows = [
                            [
                                InlineKeyboardButton(text=label, callback_data=cb)
                                for label, cb in row
                            ]
                            for row in kb_data
                        ]
                        kb = InlineKeyboardMarkup(inline_keyboard=rows)

                        await bot.send_message(
                            chat_id=admin_group_id, text=text, reply_markup=kb,
                        )
                        await esc_svc.mark_escalated(
                            mem.telegram_user_id,
                            reason=f"followup_count={mem.followup_count}",
                        )
                        sent += 1

                    except Exception as exc:
                        log.warning(
                            "admin_escalation_send_error",
                            user_id=mem.telegram_user_id,
                            error=type(exc).__name__,
                        )

                await session.commit()
            finally:
                await bot.session.close()

            if sent:
                log.info("admin_escalations_sent", count=sent)
    except Exception:
        log.exception("admin_escalation_job_error")
