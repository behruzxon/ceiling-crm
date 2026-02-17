"""
Group message handler.
Handles text messages sent inside category groups.
"""
from __future__ import annotations
from aiogram import Router, F
from aiogram.types import Message

router = Router(name="group:messages")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: Message, category: str | None, **data) -> None:
    """
    Handle incoming group messages.
    TODO: route to AI support or command handlers.
    """
    raise NotImplementedError
