"""SQLAlchemy ORM model for quotes table."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base
from shared.constants.enums import CeilingCategory


class QuoteModel(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        sa.Enum(
            CeilingCategory,
            name="ceiling_category_quotes",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    base_price_per_sqm: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    area_sqm: Mapped[float] = mapped_column(sa.Numeric(8, 2), nullable=False)
    district_modifier: Mapped[float] = mapped_column(sa.Numeric(4, 2), server_default="1.00")
    addons_detail: Mapped[list] = mapped_column(sa.JSON, server_default="[]")
    discount_pct: Mapped[float] = mapped_column(sa.Numeric(5, 2), server_default="0")
    currency: Mapped[str] = mapped_column(sa.String(8), server_default="UZS")
    is_accepted: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    created_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (sa.Index("ix_quotes_lead", "lead_id"),)
