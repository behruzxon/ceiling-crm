"""Callback handlers for agent follow-up inline buttons."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:agent_followup")


@router.callback_query(F.data.startswith("agentfu:"))
async def cb_agent_followup(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Route follow-up CTA button presses."""
    if callback.from_user is None:
        await callback.answer()
        return

    action = (callback.data or "").removeprefix("agentfu:")
    user_id = callback.from_user.id

    await callback.answer()

    if action == "order":
        from apps.bot.handlers.private.order import cmd_order_start

        if callback.message:
            await cmd_order_start(callback.message, state, **data)

    elif action == "price":
        from apps.bot.handlers.private.pricing import start_pricing_flow

        if callback.message:
            await start_pricing_flow(callback.message, state)

    elif action == "operator":
        from apps.bot.handlers.private.operator import start_operator_flow

        if callback.message:
            await start_operator_flow(callback.message, state)

    elif action == "resume":
        from apps.bot.handlers.private.order import cmd_order_start

        if callback.message:
            await cmd_order_start(callback.message, state, **data)

    elif action == "catalog":
        from apps.bot.handlers.private.catalog import cmd_catalog

        if callback.message:
            await cmd_catalog(callback.message, state, **data)

    elif action == "stop":
        try:
            from core.services.agent_memory_service import AgentMemoryService
            from core.services.followup_scheduler_service import FollowupSchedulerService
            from infrastructure.database.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                await AgentMemoryService(session).disable_followup(user_id, "user_opted_out")
                fu_svc = FollowupSchedulerService(session)
                await fu_svc.cancel_all_pending(user_id, "user_opted_out")
                await session.commit()
        except Exception:
            log.warning("followup_stop_error", user_id=user_id)

        if callback.message:
            await callback.message.answer("Tushunaman! Fikringiz o'zgarsa, istalgan vaqt yozing 😊")

    else:
        log.warning("unknown_followup_action", action=action, user_id=user_id)
