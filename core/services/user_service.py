"""
UserService — manages Telegram user profiles.
"""

from __future__ import annotations

from core.domain.user import User
from core.repositories.user_repo import AbstractUserRepository
from shared.constants.enums import UserRole
from shared.exceptions.base import NotFoundError, PermissionDeniedError
from shared.logging import get_logger

log = get_logger(__name__)

# Permission hierarchy: who can promote to which role
_PROMOTION_RULES: dict[UserRole, set[UserRole]] = {
    UserRole.SUPERADMIN: {UserRole.ADMIN, UserRole.MANAGER, UserRole.INSTALLER, UserRole.CLIENT},
    UserRole.ADMIN: {UserRole.MANAGER, UserRole.INSTALLER, UserRole.CLIENT},
}


class UserService:
    """
    Handles user registration, profile updates, and role management.
    Injected with a concrete repository implementation at startup.
    """

    def __init__(self, user_repo: AbstractUserRepository) -> None:
        self._repo = user_repo

    async def get_or_create(
        self,
        telegram_id: int,
        first_name: str,
        last_name: str | None = None,
        username: str | None = None,
        language_code: str = "uz",
        source: str | None = None,
    ) -> User:
        """
        Retrieve an existing user or create a new one.
        Called on every bot interaction via AuthMiddleware.
        """
        user = User(
            id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code,
            source=source,
        )
        result = await self._repo.upsert(user)
        log.debug("user_upserted", user_id=telegram_id, role=result.role.value)
        return result

    async def update_last_seen(self, user_id: int) -> None:
        """Update last_seen_at timestamp (handled implicitly by upsert)."""
        # The upsert in PostgresUserRepository already updates last_seen_at
        pass

    async def change_role(self, actor: User, target_user_id: int, new_role: str) -> User:
        """
        Change a user's role with permission hierarchy enforcement.

        Rules:
        - SUPERADMIN can assign any role
        - ADMIN can assign MANAGER, INSTALLER, CLIENT
        - No one can self-promote
        - No one can promote to SUPERADMIN via this method
        """
        target_role = UserRole(new_role)

        if target_role == UserRole.SUPERADMIN:
            raise PermissionDeniedError(actor.role.value, "promote_to_superadmin")

        if actor.id == target_user_id:
            raise PermissionDeniedError(actor.role.value, "self_role_change")

        allowed_targets = _PROMOTION_RULES.get(actor.role, set())
        if target_role not in allowed_targets:
            raise PermissionDeniedError(actor.role.value, f"assign_{target_role.value}")

        target = await self._repo.get_by_id(target_user_id)
        if target is None:
            raise NotFoundError("User", target_user_id)

        updated = target.model_copy(update={"role": target_role})
        result = await self._repo.update(updated)

        log.info(
            "user_role_changed",
            actor_id=actor.id,
            target_id=target_user_id,
            old_role=target.role.value,
            new_role=target_role.value,
        )
        return result

    async def get_managers(self) -> list[User]:
        """Return all active users with manager role."""
        return await self._repo.get_by_role(UserRole.MANAGER)

    async def get_installers(self) -> list[User]:
        """Return all active users with installer role."""
        return await self._repo.get_by_role(UserRole.INSTALLER)
