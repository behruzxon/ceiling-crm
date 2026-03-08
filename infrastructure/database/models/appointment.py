"""SQLAlchemy ORM model for appointments table."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base
from shared.constants.enums import AppointmentStatus, AppointmentType


class AppointmentModel(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("leads.id"), nullable=False)
    type: Mapped[str] = mapped_column(
        sa.Enum(AppointmentType, name="appointment_type"), nullable=False
    )
    installer_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    brigade_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(sa.Integer, server_default="60")
    district: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    address: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.Enum(AppointmentStatus, name="appointment_status"),
        nullable=False,
        server_default="scheduled",
    )
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_by: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    # ── Tenant ─────────────────────────────────────────────────────────────
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenants.id"), nullable=False,
    )

    __table_args__ = (
        sa.Index("ix_appointments_lead", "lead_id"),
        sa.Index("ix_appointments_installer_date", "installer_id", "scheduled_at"),
        sa.Index("ix_appointments_status", "status"),
        sa.Index("ix_appointments_tenant_id", "tenant_id"),
    )
