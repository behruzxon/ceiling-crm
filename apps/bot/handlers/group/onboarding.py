"""
Group onboarding handler.
Fires when a user joins a category group.
Detects category via GroupContextMiddleware → sends welcome card.
"""
from __future__ import annotations
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated

router = Router(name="group:onboarding")


@router.chat_member()
async def on_user_joined(event: ChatMemberUpdated, category: str | None, **data) -> None:
    """
    Handle new member joining a category group.
    TODO: implement welcome message with catalog/price/operator buttons.
    """
    raise NotImplementedError
