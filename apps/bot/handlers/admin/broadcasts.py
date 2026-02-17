"""
Admin broadcast composer handler.
Create, schedule, and send segmented broadcasts.
"""
from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from apps.bot.filters.role import RoleFilter
from shared.constants.enums import UserRole

router = Router(name="admin:broadcasts")


@router.message(Command("broadcast"), RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_broadcast(message: Message, **data) -> None:
    """Open broadcast composer. TODO: segment selector + message builder."""
    raise NotImplementedError
