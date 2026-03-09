"""
apps.bot.handlers.group.moderation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
C3-3: Link blocking with escalation.
C3-4: Flood control.

Both features share a single message handler to prevent the aiogram
propagation-stop problem (once a handler fires, the update is consumed).
Link and flood logic live in separate modules (link_guard.py,
flood_guard.py) and are imported here.
"""
from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.types import Message

from apps.bot.handlers.group._moderation import (
    dm_log,
    incr_link_violations,
    is_chat_admin,
    mute_user,
    try_delete,
)
from apps.bot.handlers.group.flood_guard import check_flood
from apps.bot.handlers.group.link_guard import has_link
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_group_settings_service
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="group:moderation")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: Message, bot: Bot, **data: object) -> None:
    """
    Combined moderation handler — C3-3 link blocking + C3-4 flood control.
    Loads group settings once. Admins are never moderated.
    """
    if message.from_user is None:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    if await is_chat_admin(bot, chat_id, user_id):
        return

    _tid = data.get("tenant_id")
    try:
        factory = get_session_factory()
        async with factory() as session:
            service = get_group_settings_service(session, tenant_id=_tid)
            settings = await service.get_or_create(chat_id)
    except Exception:
        log.warning("moderation_settings_load_failed", chat_id=chat_id)
        return

    user_name = message.from_user.full_name
    chat_title = message.chat.title or str(chat_id)

    # ── C3-3: Link blocking ───────────────────────────────────────────────
    if settings.link_block_enabled and has_link(message):
        count = await incr_link_violations(chat_id, user_id, bot_id=bot.id)
        await try_delete(message)

        if count >= 2:
            muted = await mute_user(bot, chat_id, user_id, seconds=600)
            action = "muted_10min" if muted else "deleted"
            log.info(
                "link_violation_escalated",
                chat_id=chat_id, user_id=user_id, count=count, action=action,
            )
            if settings.logs_enabled:
                asyncio.create_task(dm_log(
                    bot,
                    f"🔇 Link+mute: <b>{user_name}</b> (#{user_id}) "
                    f"→ <b>{chat_title}</b> (violation #{count})",
                ))
        else:
            log.info("link_blocked", chat_id=chat_id, user_id=user_id)
            if settings.logs_enabled:
                asyncio.create_task(dm_log(
                    bot,
                    f"🔗 Link blocked: <b>{user_name}</b> (#{user_id}) "
                    f"→ <b>{chat_title}</b>",
                ))
        return  # message already handled — skip flood check

    # ── C3-4: Flood control ───────────────────────────────────────────────
    if settings.flood_enabled and await check_flood(chat_id, user_id):
        muted = await mute_user(bot, chat_id, user_id, seconds=120)
        log.info("flood_muted", chat_id=chat_id, user_id=user_id, muted=muted)
        if settings.logs_enabled:
            asyncio.create_task(dm_log(
                bot,
                f"⚡ Flood mute 2 min: <b>{user_name}</b> (#{user_id}) "
                f"→ <b>{chat_title}</b>",
            ))
