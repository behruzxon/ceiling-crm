"""
apps.bot.handlers.group.admin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Group /admin command — C3-1: settings panel only.

Safe router contract
--------------------
This router registers exactly two handler types:
  1. Command("admin")  — only in group / supergroup chats.
  2. F.data.startswith("gs:")  — inline-button callbacks from the panel.
It does NOT register any message catch-all and will never respond to
ordinary group text.

RBAC
----
Both entry points verify Telegram admin / creator status via
bot.get_chat_member() before doing anything.  Non-admins receive a
brief ephemeral answer (callback) or no reply at all (message), so
the panel is never shown to regular members.

DM log target
-------------
BOT_ADMIN_USER_ID is available in settings for future log forwarding
(C3-2+).  Not used yet — no moderation actions in this revision.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from apps.bot.keyboards.group_admin import group_admin_keyboard
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_group_settings_service
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="group:admin")

# Telegram statuses that count as group admin.
_ADMIN_STATUSES: frozenset[str] = frozenset(
    {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    }
)


async def _is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Return True if user_id holds an admin or creator role in chat_id."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in _ADMIN_STATUSES
    except Exception:
        log.warning("get_chat_member_failed", chat_id=chat_id, user_id=user_id)
        return False


# ─── /admin command ───────────────────────────────────────────────────────────


@router.message(
    Command("admin"),
    F.chat.type.in_({"group", "supergroup"}),
)
async def cmd_group_admin(message: Message, bot: Bot, **data: object) -> None:
    """Show the settings panel to chat admins; silently ignore others."""
    if message.from_user is None:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    if not await _is_chat_admin(bot, chat_id, user_id):
        # No reply — avoids cluttering the group for regular members.
        log.debug("admin_cmd_rejected_non_admin", chat_id=chat_id, user_id=user_id)
        return

    factory = get_session_factory()
    async with factory() as session:
        service = get_group_settings_service(session)
        settings = await service.get_or_create(chat_id)

    chat_title = message.chat.title or str(chat_id)
    await message.reply(
        f"⚙️ <b>{chat_title}</b> — guruh sozlamalari\n\n"
        "Tugmani bosing — o'zgartirish darhol saqlanadi.",
        reply_markup=group_admin_keyboard(settings),
    )
    log.info("group_admin_panel_opened", chat_id=chat_id, user_id=user_id)


# ─── Toggle callbacks ─────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("gs:toggle:"))
async def handle_toggle(callback: CallbackQuery, bot: Bot, **data: object) -> None:
    """Toggle one boolean setting and refresh the keyboard in-place."""
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    if not await _is_chat_admin(bot, chat_id, user_id):
        await callback.answer("❌ Faqat guruh adminlari uchun.", show_alert=True)
        return

    field = (callback.data or "").removeprefix("gs:toggle:")

    try:
        factory = get_session_factory()
        async with factory() as session:
            service = get_group_settings_service(session)
            settings = await service.toggle(chat_id, field)
            await session.commit()
    except ValueError:
        log.warning("unknown_gs_field", field=field, chat_id=chat_id)
        await callback.answer("Noma'lum sozlama.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=group_admin_keyboard(settings))
    await callback.answer("✅ Saqlandi")


# ─── Close button ─────────────────────────────────────────────────────────────


@router.callback_query(F.data == "gs:close")
async def handle_close(callback: CallbackQuery, bot: Bot, **data: object) -> None:
    """Delete the settings panel message."""
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    if not await _is_chat_admin(bot, chat_id, user_id):
        await callback.answer("❌ Faqat guruh adminlari uchun.", show_alert=True)
        return

    await callback.message.delete()
    await callback.answer()
