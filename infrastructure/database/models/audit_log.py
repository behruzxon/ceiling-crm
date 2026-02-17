"""SQLAlchemy ORM model for audit_logs table."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.Index("ix_audit_entity", "entity_type", "entity_id"),
        sa.Index("ix_audit_actor", "actor_id"),
        sa.Index("ix_audit_created", "created_at"),
    )
