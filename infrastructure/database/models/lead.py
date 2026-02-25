"""SQLAlchemy ORM model for leads table."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base
from shared.constants.enums import CeilingCategory, LeadSource


class LeadModel(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(
        sa.Enum(
            CeilingCategory,
            name="ceiling_category",
            # Use enum .value ("matviy_oq") not .name ("MATTE_WHITE") when
            # serialising to SQL.  The DB enum was created with value-strings,
            # so without this SQLAlchemy sends the wrong literal and Postgres
            # raises: invalid input value for enum ceiling_category: "MATTE_WHITE"
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    source_group_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("groups.id"), nullable=True)
    source: Mapped[str] = mapped_column(
        sa.Enum(
            LeadSource,
            name="lead_source",
            # Same fix: DB stores "deeplink" not "DEEPLINK".
            values_callable=lambda obj: [e.value for e in obj],
        ),
        server_default="group",
    )
    name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    phone: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    district: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    room_length: Mapped[float | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    room_width: Mapped[float | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    room_area: Mapped[float | None] = mapped_column(sa.Numeric(8, 2), nullable=True)
    addons: Mapped[dict] = mapped_column(sa.JSON, server_default="{}")
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    assigned_manager_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
