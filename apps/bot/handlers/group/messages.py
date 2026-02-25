"""
Group message handler.
Handles text messages sent inside category groups.
"""
from __future__ import annotations
from aiogram import Router, F
from aiogram.types import Message
from shared.logging import get_logger

log = get_logger(__name__)

router = Router(name="group:messages")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: Message, category: str | None, **data) -> None:
    """Silently ignore group text messages; join events handled by onboarding router."""
    # TODO: remove debug logging
    log.debug("group_message_received", chat_id=message.chat.id)
