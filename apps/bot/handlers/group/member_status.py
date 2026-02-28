"""
Group member status change handler.
Tracks bot add/remove events and logs status changes.

User join analytics (upsert_join) live in welcome.py so that both the
welcome message and the analytics record are driven by the same
chat_member event without competing handlers consuming the update.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import ChatMemberUpdated

from shared.logging import get_logger

router = Router(name="group:member_status")
log = get_logger(__name__)


@router.my_chat_member()
async def on_bot_status_change(event: ChatMemberUpdated, **data: object) -> None:
    """Log when the bot is added to or removed from any group."""
    log.info(
        "bot_status_changed",
        chat_id=event.chat.id,
        chat_title=event.chat.title,
        old_status=event.old_chat_member.status,
        new_status=event.new_chat_member.status,
    )
