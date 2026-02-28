"""
Auto-capture groups where the bot has admin privileges.

Listens to my_chat_member updates.  When the bot is promoted to
administrator in a group or supergroup, the chat is recorded via
AdminGroupService.  No messages are ever sent to the group.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import ChatMemberUpdated

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_admin_group_service
from shared.config import get_settings
from shared.logging import get_logger

router = Router(name="group:admin_group_tracker")
log = get_logger(__name__)


class _IsAdminGroupPromotion(BaseFilter):
    """Passes only when the bot is promoted to admin in the designated admin group.

    Encoding this as a decorator-level filter (rather than runtime guards inside
    the handler body) is critical: when a filter rejects an event, aiogram skips
    this handler entirely and continues to the next one.  A plain early ``return``
    inside the body still *consumes* the update and blocks downstream handlers.
    """

    async def __call__(self, event: ChatMemberUpdated) -> bool:
        return (
            event.chat.type in ("group", "supergroup")
            and event.new_chat_member.status == "administrator"
            and event.chat.id == get_settings().bot.admin_group_id
        )


@router.my_chat_member(_IsAdminGroupPromotion())
async def track_bot_admin_status(event: ChatMemberUpdated, **data: object) -> None:
    """Record the admin group when the bot is promoted there.

    Only fires for the designated admin group (enforced by filter).
    Deliberately silent — never replies in the group.
    """
    chat = event.chat
    title = chat.title or str(chat.id)
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = get_admin_group_service(session)
            await svc.upsert_admin_group(chat_id=chat.id, title=title)
            await session.commit()
    except Exception:
        log.exception("admin_group_tracker_failed", chat_id=chat.id)
