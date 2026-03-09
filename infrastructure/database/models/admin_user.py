"""AdminUserModel — web admin panel users (separate from Telegram UserModel).

Each tenant can have one or more admin panel accounts with email + bcrypt password.
These are distinct from the Telegram-based UserModel (which tracks bot users).
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AdminUserModel(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenants.id"), nullable=False,
    )
    email: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "email", name="uq_admin_users_tenant_email"),
        sa.Index("ix_admin_users_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<AdminUserModel id={self.id} email={self.email!r} tenant_id={self.tenant_id}>"
