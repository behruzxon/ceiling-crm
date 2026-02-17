"""
Admin scheduler management handler.
View and manage scheduled appointments and jobs.
"""
from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from apps.bot.filters.role import RoleFilter
from shared.constants.enums import UserRole

router = Router(name="admin:scheduler")


@router.message(Command("schedule"), RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_schedule(message: Message, **data) -> None:
    """View today's and upcoming appointments. TODO: calendar view."""
    raise NotImplementedError
