"""SQLAlchemy ORM model for Telegram groups table."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base
from shared.constants.enums import CeilingCategory


class GroupModel(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    category: Mapped[str] = mapped_column(
        sa.Enum(
            CeilingCategory,
            name="ceiling_category_groups",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    invite_link: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true")
    member_count: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
