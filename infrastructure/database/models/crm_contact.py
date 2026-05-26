"""SQLAlchemy ORM model for crm_contacts table."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base


class CRMContactModel(Base):
    __tablename__ = "crm_contacts"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True, unique=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    username: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    language_code: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    source: Mapped[str | None] = mapped_column(sa.String(30), nullable=True)
    lead_status: Mapped[str] = mapped_column(sa.String(30), server_default="new")
    lead_score: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    temperature: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    __table_args__ = (
        sa.Index("ix_crm_contact_status", "lead_status"),
        sa.Index("ix_crm_contact_temp", "temperature"),
        sa.Index("ix_crm_contact_last_msg", "last_message_at"),
    )
