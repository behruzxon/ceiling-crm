"""SQLAlchemy ORM model for crm_operator_outbound_audit."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class CRMOperatorOutboundAuditModel(Base):
    __tablename__ = "crm_operator_outbound_audit"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    contact_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    operator_id: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    message_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    message_preview: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_crm_audit_contact", "contact_id", "created_at"),
        sa.Index("ix_crm_audit_status", "status", "created_at"),
    )
