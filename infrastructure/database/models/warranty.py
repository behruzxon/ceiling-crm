"""SQLAlchemy ORM model for warranties table.

One warranty per lead (UNIQUE constraint on lead_id).
issued_at + expires_at are bare DATE columns — no time-zone needed for
calendar-based validity (15-year warranty from installation date).
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class WarrantyModel(Base):
    __tablename__ = "warranties"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    issued_at: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expires_at: Mapped[date] = mapped_column(sa.Date, nullable=False)
    warranty_card_no: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("ix_warranties_lead", "lead_id"),
        sa.Index("ix_warranties_expires_at", "expires_at"),
    )
