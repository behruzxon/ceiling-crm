"""SQLAlchemy ORM model for users table."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base
from shared.constants.enums import UserRole


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    last_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(20), nullable=True, unique=True)
    language_code: Mapped[str] = mapped_column(sa.String(8), server_default="uz")
    role: Mapped[str] = mapped_column(
        sa.Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False, server_default="client"
    )
    source: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    referral_code: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_users_username", "username"),
        sa.Index("ix_users_role", "role"),
    )
