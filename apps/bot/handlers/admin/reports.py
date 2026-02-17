"""
Admin analytics and reports handler.
Generate and export business reports.
"""
from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from apps.bot.filters.role import RoleFilter
from shared.constants.enums import UserRole

router = Router(name="admin:reports")


@router.message(Command("report"), RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_report(message: Message, **data) -> None:
    """Generate analytics report. TODO: date range selector + export format."""
    raise NotImplementedError
