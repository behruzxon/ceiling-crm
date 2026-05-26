"""SQLAlchemy ORM models for admin_users and admin_audit_logs."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base

class AdminUserModel(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    admin_id: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    role: Mapped[str] = mapped_column(sa.String(20), server_default="viewer")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"))
    is_super_owner: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("false"))
    permissions_override_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    __table_args__ = (sa.Index("ix_admin_user_role", "role"), sa.Index("ix_admin_user_active", "is_active"))


class AdminAuditLogModel(Base):
    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    actor_admin_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), server_default="success")
    reason: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    __table_args__ = (
        sa.Index("ix_admin_audit_actor", "actor_admin_id", "created_at"),
        sa.Index("ix_admin_audit_action", "action", "created_at"),
        sa.Index("ix_admin_audit_status", "status", "created_at"),
    )
