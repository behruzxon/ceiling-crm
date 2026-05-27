"""SQLAlchemy ORM models for admin_sessions and admin_login_attempts."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AdminSessionModel(Base):
    __tablename__ = "admin_sessions"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    session_id_hash: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    admin_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    role: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), server_default="active")
    ip_address: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    __table_args__ = (
        sa.Index("ix_admin_session_admin_created", "admin_id", "created_at"),
        sa.Index("ix_admin_session_status_expires", "status", "expires_at"),
        sa.Index("ix_admin_session_last_seen", "last_seen_at"),
    )


class AdminLoginAttemptModel(Base):
    __tablename__ = "admin_login_attempts"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    admin_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    __table_args__ = (
        sa.Index("ix_admin_login_admin_created", "admin_id", "created_at"),
        sa.Index("ix_admin_login_ip_created", "ip_address", "created_at"),
        sa.Index("ix_admin_login_status_created", "status", "created_at"),
    )
