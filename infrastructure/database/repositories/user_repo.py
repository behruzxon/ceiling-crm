"""PostgreSQL implementation of AbstractUserRepository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.user import User
from core.repositories.user_repo import AbstractUserRepository
from infrastructure.database.models.user import UserModel
from shared.constants.enums import UserRole


class PostgresUserRepository(AbstractUserRepository):
    """Concrete SQLAlchemy/PostgreSQL user repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, model: UserModel) -> User:
        """Convert ORM model to immutable domain object."""
        return User(
            id=model.id,
            username=model.username,
            first_name=model.first_name,
            last_name=model.last_name,
            phone=model.phone,
            language_code=model.language_code,
            role=UserRole(model.role) if isinstance(model.role, str) else model.role,
            source=model.source,
            is_blocked=model.is_blocked,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_seen_at=model.last_seen_at,
        )

    async def get_by_id(self, id: int) -> User | None:
        """SELECT user by primary key (Telegram user_id)."""
        result = await self._session.get(UserModel, id)
        return self._to_domain(result) if result else None

    async def get_by_username(self, username: str) -> User | None:
        """SELECT user by Telegram username."""
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def upsert(self, user: User) -> User:
        """INSERT ... ON CONFLICT DO UPDATE for Telegram user.

        Raises ValueError for non-positive IDs (groups / channels / service
        entities) so the bug is caught loudly at the repository boundary even
        if a future caller bypasses the AuthMiddleware guard.
        """
        if user.id <= 0:
            raise ValueError(
                f"upsert() called with non-positive user id={user.id}. "
                "Only private Telegram users (id > 0) may be stored in `users`."
            )
        stmt = (
            insert(UserModel)
            .values(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone,
                language_code=user.language_code,
                role=user.role.value,
                source=user.source,
                is_blocked=user.is_blocked,
                last_seen_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code,
                    "last_seen_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                },
            )
            .returning(UserModel)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one()
        return self._to_domain(model)

    async def get_by_role(self, role: UserRole) -> list[User]:
        """Return all active users with the given role."""
        stmt = (
            select(UserModel)
            .where(UserModel.role == role, UserModel.is_blocked.is_(False))
            .order_by(UserModel.first_name)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_active(self) -> int:
        """Count all non-blocked users."""
        stmt = select(func.count()).select_from(UserModel).where(UserModel.is_blocked.is_(False))
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: User) -> User:
        """Insert a new user record."""
        model = UserModel(
            id=entity.id,
            username=entity.username,
            first_name=entity.first_name,
            last_name=entity.last_name,
            phone=entity.phone,
            language_code=entity.language_code,
            role=entity.role.value,
            source=entity.source,
            is_blocked=entity.is_blocked,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update(self, entity: User) -> User:
        """Update an existing user record."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == entity.id)
            .values(
                username=entity.username,
                first_name=entity.first_name,
                last_name=entity.last_name,
                phone=entity.phone,
                language_code=entity.language_code,
                role=entity.role.value,
                source=entity.source,
                is_blocked=entity.is_blocked,
                updated_at=datetime.now(UTC),
            )
            .returning(UserModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        return self._to_domain(model)

    async def delete(self, id: int) -> bool:
        """Soft delete: set is_blocked=True."""
        stmt = (
            update(UserModel)
            .where(UserModel.id == id)
            .values(is_blocked=True, updated_at=datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
