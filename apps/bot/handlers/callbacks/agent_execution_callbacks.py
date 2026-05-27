"""Admin callbacks for agent execution approval queue."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:agent_execution")


def _is_admin(user_id: int) -> bool:
    settings = get_settings()
    admin_id = settings.bot.admin_user_id
    return admin_id is not None and user_id == admin_id


@router.callback_query(F.data.startswith("agentexec:approve:"))
async def cb_approve(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not _is_admin(callback.from_user.id):
        if callback.message:
            await callback.message.answer("Bu tugma faqat adminlar uchun.")
        return

    execution_id = (callback.data or "").split(":", 2)[-1]
    if not execution_id:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_execution_queue_service import (
                AgentExecutionQueueService,
            )

            svc = AgentExecutionQueueService(session)
            ok, reason = await svc.approve(execution_id, callback.from_user.id)
            await session.commit()

        msg = f"✅ Approved: {execution_id}" if ok else f"⚠️ {reason}"
        if callback.message:
            await callback.message.answer(msg)
    except Exception:
        log.warning("agent_exec_approve_error", execution_id=execution_id)


@router.callback_query(F.data.startswith("agentexec:reject:"))
async def cb_reject(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not _is_admin(callback.from_user.id):
        if callback.message:
            await callback.message.answer("Bu tugma faqat adminlar uchun.")
        return

    execution_id = (callback.data or "").split(":", 2)[-1]
    if not execution_id:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_execution_queue_service import (
                AgentExecutionQueueService,
            )

            svc = AgentExecutionQueueService(session)
            ok, reason = await svc.reject(execution_id, callback.from_user.id)
            await session.commit()

        msg = f"❌ Rejected: {execution_id}" if ok else f"⚠️ {reason}"
        if callback.message:
            await callback.message.answer(msg)
    except Exception:
        log.warning("agent_exec_reject_error", execution_id=execution_id)


@router.callback_query(F.data.startswith("agentexec:view:"))
async def cb_view(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not _is_admin(callback.from_user.id):
        if callback.message:
            await callback.message.answer("Bu tugma faqat adminlar uchun.")
        return

    execution_id = (callback.data or "").split(":", 2)[-1]
    if not execution_id:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_execution_queue_service import (
                AgentExecutionQueueService,
            )

            svc = AgentExecutionQueueService(session)
            record = await svc.get_by_execution_id(execution_id)

        if record is None:
            if callback.message:
                await callback.message.answer("Record topilmadi.")
            return

        msg = AgentExecutionQueueService.build_admin_approval_message(record)
        if callback.message:
            await callback.message.answer(msg)
    except Exception:
        log.warning("agent_exec_view_error", execution_id=execution_id)
