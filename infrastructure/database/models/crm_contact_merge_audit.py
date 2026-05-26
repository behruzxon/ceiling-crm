"""SQLAlchemy ORM model for crm_contact_merge_audit."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base


class CRMContactMergeAuditModel(Base):
    __tablename__ = "crm_contact_merge_audit"
    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    source_contact_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    target_contact_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    actor_admin_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    confidence: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    reasons_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    merge_plan_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    before_source_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    before_target_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    merged_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    __table_args__ = (
        sa.Index("ix_merge_audit_source", "source_contact_id"),
        sa.Index("ix_merge_audit_target", "target_contact_id"),
        sa.Index("ix_merge_audit_status", "status"),
        sa.Index("ix_merge_audit_created", "created_at"),
    )
