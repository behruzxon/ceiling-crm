"""
Role-based access filter.
Usage: @router.message(Command("x"), RoleFilter(UserRole.ADMIN))
"""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from core.domain.user import User
from shared.constants.enums import UserRole


class RoleFilter(BaseFilter):
    """
    Passes only if the authenticated user's role is in required_roles.
    Requires AuthMiddleware to have run first (injects db_user).
    """

    def __init__(self, *required_roles: UserRole) -> None:
        self.required_roles = frozenset(required_roles)

    async def __call__(
        self, event: TelegramObject, db_user: User | None = None, **data: object
    ) -> bool:
        if db_user is None:
            return False
        return db_user.role in self.required_roles
