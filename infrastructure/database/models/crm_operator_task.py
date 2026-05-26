"""SQLAlchemy ORM model for crm_operator_tasks."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base

class CRMOperatorTaskModel(Base):
    __tablename__ = "crm_operator_tasks"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    task_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), server_default="todo")
    priority: Mapped[str] = mapped_column(sa.String(20), server_default="normal")
    due_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    created_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    source: Mapped[str] = mapped_column(sa.String(20), server_default="manual")
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_task_contact_status", "contact_id", "status"),
        sa.Index("ix_task_status_due", "status", "due_at"),
        sa.Index("ix_task_priority_due", "priority", "due_at"),
    )
