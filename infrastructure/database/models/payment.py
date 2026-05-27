"""SQLAlchemy ORM model for payments table.

One row per payment attempt for a lead.
A lead may have multiple payment rows (e.g. partial payments, refunds).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base
from shared.constants.enums import PaymentMethod, PaymentStatus


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Amount in UZS (so'm), integer — no fractional currency",
    )
    method: Mapped[str] = mapped_column(
        sa.Enum(
            PaymentMethod, name="payment_method", values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        sa.Enum(
            PaymentStatus, name="payment_status", values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        server_default="pending",
    )
    paid_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    proof_file_id: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.Index("ix_payments_lead", "lead_id"),
        sa.Index("ix_payments_status", "status"),
        sa.Index("ix_payments_paid_at", "paid_at"),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
    )
