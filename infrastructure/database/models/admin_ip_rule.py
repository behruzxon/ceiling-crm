"""SQLAlchemy ORM model for admin_ip_access_rules."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base


class AdminIPAccessRuleModel(Base):
    __tablename__ = "admin_ip_access_rules"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    ip_pattern: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"))
    created_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    __table_args__ = (
        sa.Index("ix_ip_rule_pattern", "ip_pattern"),
        sa.Index("ix_ip_rule_type", "rule_type"),
        sa.Index("ix_ip_rule_active", "is_active"),
        sa.Index("ix_ip_rule_created", "created_at"),
    )
