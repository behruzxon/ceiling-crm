"""SQLAlchemy ORM models for crm_messages, crm_contact_notes, crm_contact_tags."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class CRMMessageModel(Base):
    __tablename__ = "crm_messages"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    contact_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    direction: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    sender_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    message_type: Mapped[str] = mapped_column(sa.String(20), server_default="text")
    payload_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    redacted_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.Index("ix_crm_msg_contact_created", "contact_id", "created_at"),
        sa.Index("ix_crm_msg_user_created", "telegram_user_id", "created_at"),
        sa.Index("ix_crm_msg_direction", "direction"),
    )


class CRMContactNoteModel(Base):
    __tablename__ = "crm_contact_notes"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    contact_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    note_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)


class CRMContactTagModel(Base):
    __tablename__ = "crm_contact_tags"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    contact_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    tag: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.UniqueConstraint("contact_id", "tag", name="uq_contact_tag"),
    )
