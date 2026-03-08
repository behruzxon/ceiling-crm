"""SQLAlchemy ORM model for subscription_payments table.

Tracks tenant subscription payment lifecycle through external providers
(Click.uz, Payme.uz) or manual superadmin actions.
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base
from shared.constants.enums import SubscriptionPaymentProvider, SubscriptionPaymentStatus


class SubscriptionPaymentModel(Base):
    __tablename__ = "subscription_payments"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        sa.Enum(
            SubscriptionPaymentProvider,
            name="sub_payment_provider",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        sa.Enum(
            SubscriptionPaymentStatus,
            name="sub_payment_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        server_default="pending",
    )

    amount: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False,
        comment="Amount in UZS (so'm), integer",
    )
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="UZS")
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Provider-specific IDs
    merchant_trans_id: Mapped[str] = mapped_column(
        sa.String(128), nullable=False, unique=True,
        comment="Our unique transaction ID sent to provider",
    )
    provider_trans_id: Mapped[str | None] = mapped_column(
        sa.String(128), nullable=True,
        comment="Transaction ID from Click/Payme",
    )

    # Subscription extension metadata
    extension_days: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="30",
    )

    # Timestamps
    paid_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    # Extra JSON for provider-specific metadata (sign_time, error codes, etc.)
    provider_meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}",
    )

    __table_args__ = (
        sa.Index("ix_sub_payments_tenant_id", "tenant_id"),
        sa.Index("ix_sub_payments_status", "status"),
        sa.Index("ix_sub_payments_provider_trans_id", "provider_trans_id"),
    )
