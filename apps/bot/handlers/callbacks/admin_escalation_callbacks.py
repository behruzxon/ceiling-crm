"""Callback handlers for admin escalation alert buttons."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:admin_escalation")


def _is_admin(user_id: int) -> bool:
    try:
        from shared.config import get_settings
        settings = get_settings()
        admin_id = settings.bot.admin_user_id
        return admin_id is not None and user_id == admin_id
    except Exception:
        return False


@router.callback_query(F.data.startswith("agentesc:"))
async def cb_admin_escalation(callback: CallbackQuery, **data: object) -> None:
    """Handle admin escalation button presses."""
    if callback.from_user is None:
        await callback.answer()
        return

    caller_id = callback.from_user.id
    if not _is_admin(caller_id):
        await callback.answer("Bu tugma faqat adminlar uchun.", show_alert=True)
        return

    raw = (callback.data or "").removeprefix("agentesc:")
    parts = raw.rsplit(":", 1)
    if len(parts) != 2:
        await callback.answer()
        return

    action, uid_str = parts
    try:
        target_user_id = int(uid_str)
    except ValueError:
        await callback.answer()
        return

    await callback.answer()

    if action == "contacted":
        try:
            from core.services.admin_escalation_service import AdminEscalationService
            from infrastructure.database.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                svc = AdminEscalationService(session)
                await svc.mark_escalated(target_user_id, "admin_contacted")
                await session.commit()
        except Exception:
            log.warning("escalation_contacted_error", target=target_user_id)

        if callback.message:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>Admin bog'landi</b>",
            )

    elif action == "stop":
        try:
            from core.services.agent_memory_service import AgentMemoryService
            from core.services.followup_scheduler_service import FollowupSchedulerService
            from infrastructure.database.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                await AgentMemoryService(session).disable_followup(
                    target_user_id, "admin_marked_stop",
                )
                await FollowupSchedulerService(session).cancel_all_pending(
                    target_user_id, "admin_marked_stop",
                )
                await session.commit()
        except Exception:
            log.warning("escalation_stop_error", target=target_user_id)

        if callback.message:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>Admin: kerak emas</b>",
            )

    elif action == "write":
        if callback.message:
            link = f"tg://user?id={target_user_id}"
            await callback.message.answer(
                f"💬 <a href=\"{link}\">Mijozga yozish</a>",
            )

    else:
        log.warning("unknown_escalation_action", action=action)
