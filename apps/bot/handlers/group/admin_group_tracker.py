"""
Auto-capture groups where the bot has admin privileges.

Listens to my_chat_member updates.  When the bot is promoted to
administrator in a group or supergroup, the chat is recorded via
AdminGroupService.  No messages are ever sent to the group.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import ChatMemberUpdated

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_admin_group_service
from shared.logging import get_logger

router = Router(name="group:admin_group_tracker")
log = get_logger(__name__)


@router.my_chat_member()
async def track_bot_admin_status(event: ChatMemberUpdated, **data: object) -> None:
    """Record or refresh a group entry when the bot becomes admin.

    Deliberately silent — never replies in the group.
    """
    chat = event.chat
    if chat.type not in ("group", "supergroup"):
        return

    new_status = event.new_chat_member.status
    if new_status != "administrator":
        # Bot was removed, restricted, or made a plain member — no action needed.
        return

    title = chat.title or str(chat.id)
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = get_admin_group_service(session)
            await svc.upsert_admin_group(chat_id=chat.id, title=title)
            await session.commit()
    except Exception:
        log.exception("admin_group_tracker_failed", chat_id=chat.id)
