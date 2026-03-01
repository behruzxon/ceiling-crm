"""
Auto-capture groups where the bot has admin privileges.
Sends the main menu keyboard whenever the bot joins or is promoted in any group.

Listens to my_chat_member updates.  When the bot gains membership:
- Records the chat in admin_groups if it is the designated admin group and
  the bot has been promoted to administrator.
- Sends "Menyu:" with the persistent reply keyboard to all groups.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import ChatMemberUpdated

from apps.bot.keyboards.main_menu import main_menu_keyboard
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_admin_group_service
from shared.config import get_settings
from shared.logging import get_logger

router = Router(name="group:admin_group_tracker")
log = get_logger(__name__)

_MENU_KB = main_menu_keyboard()


class _IsBotGainingAccess(BaseFilter):
    """Passes when the bot gains membership (added or promoted) in any group/supergroup.

    Covers two transitions:
    - Bot is added to a group (old status: left/kicked/restricted → new: member/administrator)
    - Bot is promoted from member to administrator
    """

    async def __call__(self, event: ChatMemberUpdated) -> bool:
        if event.chat.type not in ("group", "supergroup"):
            return False
        new_status = event.new_chat_member.status
        old_status = event.old_chat_member.status
        # Bot freshly added (was not an active member before)
        added = (
            new_status in ("member", "administrator")
            and old_status not in ("member", "administrator")
        )
        # Bot promoted from plain member to administrator
        promoted = new_status == "administrator" and old_status == "member"
        return added or promoted


@router.my_chat_member(_IsBotGainingAccess())
async def track_bot_group_entry(event: ChatMemberUpdated, **data: object) -> None:
    """When the bot joins or is promoted in a group:

    1. If it's the designated admin group and status is administrator →
       upsert the record in admin_groups table.
    2. Send "Menyu:" with the persistent reply keyboard to the group.
    """
    chat = event.chat
    new_status = event.new_chat_member.status

    log.info(
        "bot_status_changed",
        chat_id=chat.id,
        chat_title=chat.title,
        old_status=event.old_chat_member.status,
        new_status=new_status,
    )

    # Record the designated admin group when promoted there
    settings = get_settings()
    if chat.id == settings.bot.admin_group_id and new_status == "administrator":
        title = chat.title or str(chat.id)
        try:
            factory = get_session_factory()
            async with factory() as session:
                svc = get_admin_group_service(session)
                await svc.upsert_admin_group(chat_id=chat.id, title=title)
                await session.commit()
        except Exception:
            log.exception("admin_group_tracker_failed", chat_id=chat.id)

    # Send menu keyboard to the group
    try:
        await event.bot.send_message(
            chat_id=chat.id,
            text="Menyu:",
            reply_markup=_MENU_KB,
        )
        log.info("group_menu_sent", chat_id=chat.id)
    except Exception:
        log.exception("group_menu_send_failed", chat_id=chat.id)
