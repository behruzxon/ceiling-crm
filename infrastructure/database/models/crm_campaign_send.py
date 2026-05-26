"""SQLAlchemy ORM model for crm_campaign_send_attempts."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base


class CRMCampaignSendAttemptModel(Base):
    __tablename__ = "crm_campaign_send_attempts"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    campaign_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    contact_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    telegram_chat_id_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(20), server_default="telegram")
    message_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    message_preview: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    __table_args__ = (
        sa.Index("ix_send_campaign_created", "campaign_id", "created_at"),
        sa.Index("ix_send_campaign_status", "campaign_id", "status"),
        sa.Index("ix_send_contact_created", "contact_id", "created_at"),
        sa.Index("ix_send_batch", "batch_id"),
        sa.Index("ix_send_status_created", "status", "created_at"),
    )
