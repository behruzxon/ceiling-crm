"""
apps.bot.handlers.group.welcome
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
C3-2: Welcome message with auto-delete on new member joins.

Behaviour
---------
- Fires on chat_member events where a non-bot user transitions to MEMBER
  status from a LEFT or KICKED state.
- If welcome_enabled=False → silent, no-op.
- Sends a short Uzbek welcome mentioning the joined user.
- Schedules auto-deletion after settings.welcome_autodelete_seconds.
  If the bot lacks delete permission the deletion silently fails (logged).
- If logs_enabled=True, sends a DM log to BOT_ADMIN_USER_ID.
"""
from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import (
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from apps.bot.handlers.group._moderation import dm_log, try_delete
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_group_join_repo, get_group_settings_service
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="group:welcome")


@router.chat_member(
    F.chat.type.in_({"group", "supergroup"}),
    F.new_chat_member.status == ChatMemberStatus.MEMBER,
    F.new_chat_member.user.is_bot == False,  # noqa: E712 — aiogram magic filter
    F.old_chat_member.status.in_({ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}),
)
async def on_user_joined(event: ChatMemberUpdated, bot: Bot, **data: object) -> None:
    """Send a welcome message and schedule its auto-deletion."""
    chat_id = event.chat.id

    try:
        factory = get_session_factory()
        async with factory() as session:
            service = get_group_settings_service(session)
            settings = await service.get_or_create(chat_id)
    except Exception:
        log.warning("welcome_settings_load_failed", chat_id=chat_id)
        return

    joined = event.new_chat_member.user

    # ── Join analytics (independent of welcome_enabled) ──────────────────
    # Runs for the main customer group only.  Non-fatal — a DB failure must
    # never prevent the welcome message from being sent.
    _main_gid = get_settings().bot.main_group_id
    if _main_gid and event.chat.id == _main_gid and joined.id > 0:
        try:
            async with get_session_factory()() as _s:
                await get_group_join_repo(_s).upsert_join(
                    group_id=_main_gid,
                    user_id=joined.id,
                    joined_at=event.date,
                )
                await _s.commit()
            log.info("group_join_recorded", group_id=_main_gid, user_id=joined.id)
        except Exception:
            log.exception("group_join_record_error", group_id=_main_gid, user_id=joined.id)

    if not settings.welcome_enabled:
        return
    mention = f"<a href='tg://user?id={joined.id}'>{joined.full_name}</a>"
    chat_title = event.chat.title or str(chat_id)

    text = (
        f"👋 Assalomu alaykum, {mention}!\n\n"
        "VashPotolok kompaniyasining rasmiy savol-javob guruhiga xush kelibsiz.\n\n"
        "Bu yerda:\n"
        "• 📐 Potolok bo'yicha savollar berishingiz mumkin\n"
        "• 📸 Rasm yuborib maslahat olishingiz mumkin\n"
        "• 👷‍♂️ Mutaxassislar javob beradi\n\n"
        "📩 Narx hisoblash va katalog uchun:\n"
        "👉 @potolok_x_bot\n\n"
        "🚫 Reklama va linklar taqiqlanadi."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📐 Narx hisoblash",
            url="https://t.me/potolok_x_bot?start=price",
        ),
        InlineKeyboardButton(
            text="📂 Katalog",
            url="https://t.me/potolok_x_bot?start=catalog",
        ),
    ]])

    try:
        msg = await bot.send_message(
            chat_id, text, parse_mode="HTML", reply_markup=keyboard
        )
    except Exception as exc:
        log.warning("welcome_send_failed", chat_id=chat_id, error=str(exc))
        return

    log.info("welcome_sent", chat_id=chat_id, user_id=joined.id)

    if settings.logs_enabled:
        asyncio.create_task(dm_log(
            bot,
            f"👤 Yangi a'zo: {mention} → <b>{chat_title}</b> "
            f"(<code>{chat_id}</code>)",
        ))

    delete_after = settings.welcome_autodelete_seconds
    if delete_after > 0:
        async def _auto_delete() -> None:
            await asyncio.sleep(delete_after)
            await try_delete(msg)

        asyncio.create_task(_auto_delete())
