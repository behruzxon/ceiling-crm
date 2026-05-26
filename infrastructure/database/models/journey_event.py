"""SQLAlchemy ORM model for customer_journey_events table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class JourneyEventModel(Base):
    __tablename__ = "customer_journey_events"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    event_data: Mapped[dict] = mapped_column(sa.JSON, server_default="{}", nullable=False)
    source_handler: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_journey_user_created", "user_id", "created_at"),
        sa.Index("ix_journey_type_created", "event_type", "created_at"),
    )
