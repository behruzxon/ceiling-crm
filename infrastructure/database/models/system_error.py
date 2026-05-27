"""SQLAlchemy ORM model for system_errors table.

Stores unhandled exceptions from bot handlers, scheduler jobs,
and background tasks for post-mortem analysis.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class SystemErrorModel(Base):
    __tablename__ = "system_errors"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    service: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    error_type: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    stacktrace: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.Index("ix_system_errors_service", "service"),
        sa.Index("ix_system_errors_created_at", "created_at"),
    )
