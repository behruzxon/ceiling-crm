"""
Track groups where the bot has admin privileges.

Listens to my_chat_member updates for group and supergroup chats:
  - Bot becomes administrator/creator → UPSERT into admin_groups.
  - Bot loses admin (demoted to member) or leaves/is kicked → DELETE from admin_groups.

Additionally sends the persistent URL InlineKeyboard to the group whenever the bot
gains an active presence (freshly added or promoted from member to admin).
When the bot becomes admin it also tries to pin the menu message.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import ChatMemberUpdated

from apps.bot.keyboards.main_menu import group_menu_kb_full
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_admin_group_service
from shared.logging import get_logger

router = Router(name="group:admin_group_tracker")
log = get_logger(__name__)


@router.my_chat_member()
async def track_bot_group_membership(event: ChatMemberUpdated, **data: object) -> None:
    """Handle every bot status change inside a group or supergroup.

    Upsert/remove from admin_groups based on the new admin status, and
    send (and optionally pin) the URL inline menu keyboard when the bot
    first gains presence.
    """
    if event.chat.type not in ("group", "supergroup"):
        return

    chat = event.chat
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status
    title = chat.title or ""

    log.info(
        "bot_status_changed",
        chat_id=chat.id,
        chat_title=title,
        old_status=old_status,
        new_status=new_status,
    )

    # ── Admin-group tracking ───────────────────────────────────────────────
    _tid = data.get("tenant_id")

    if new_status in ("administrator", "creator"):
        # Bot is now admin/owner of this group — record it for ADMIN_GROUPS broadcasts.
        try:
            factory = get_session_factory()
            async with factory() as session:
                svc = get_admin_group_service(session, tenant_id=_tid)
                await svc.upsert_admin_group(chat_id=chat.id, title=title)
                await session.commit()
        except Exception:
            log.exception("admin_group_tracker_failed", chat_id=chat.id)

    elif old_status in ("administrator", "creator"):
        # Bot WAS admin but is no longer — remove so it no longer receives
        # ADMIN_GROUPS broadcasts (covers demotion, kick, and voluntary leave).
        try:
            factory = get_session_factory()
            async with factory() as session:
                svc = get_admin_group_service(session, tenant_id=_tid)
                await svc.remove_admin_group(chat_id=chat.id)
                await session.commit()
        except Exception:
            log.exception("admin_group_remove_failed", chat_id=chat.id)

    # ── Persistent menu keyboard ───────────────────────────────────────────
    # Send the URL InlineKeyboard when the bot gains an active presence:
    #   • freshly added as member or admin (was not previously an active member)
    #   • promoted from plain member to administrator
    gained_access = (
        new_status in ("member", "administrator")
        and old_status not in ("member", "administrator", "creator")
    ) or (new_status == "administrator" and old_status == "member")

    if gained_access:
        try:
            kb = group_menu_kb_full()
            msg = await event.bot.send_message(
                chat_id=chat.id,
                text="📌 Menyu — barcha bo'limlar:",
                reply_markup=kb,
            )
            log.info("group_menu_sent", chat_id=chat.id)

            # Pin the menu when bot has admin rights (ignore permission errors)
            if new_status in ("administrator", "creator"):
                try:
                    await event.bot.pin_chat_message(
                        chat_id=chat.id,
                        message_id=msg.message_id,
                        disable_notification=True,
                    )
                    log.info("group_menu_pinned", chat_id=chat.id)
                except Exception:
                    log.warning("group_menu_pin_failed", chat_id=chat.id)
        except Exception:
            log.exception("group_menu_send_failed", chat_id=chat.id)
