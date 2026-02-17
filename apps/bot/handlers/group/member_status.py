"""
Group member status change handler.
Tracks join / leave / ban events for analytics.
"""
from __future__ import annotations
from aiogram import Router
from aiogram.types import ChatMemberUpdated

from shared.logging import get_logger

router = Router(name="group:member_status")
log = get_logger(__name__)


@router.my_chat_member()
async def on_bot_status_change(event: ChatMemberUpdated, **data) -> None:
    """Log when the bot is added to or removed from a group."""
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    log.info(
        "bot_status_changed",
        chat_id=event.chat.id,
        chat_title=event.chat.title,
        old_status=old_status,
        new_status=new_status,
    )
