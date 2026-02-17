"""SQLAlchemy ORM model for pipeline_stages table."""
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.database.session import Base
from shared.constants.enums import PipelineStage


class PipelineStageModel(Base):
    __tablename__ = "pipeline_stages"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("leads.id"), nullable=False)
    stage: Mapped[str] = mapped_column(sa.Enum(PipelineStage, name="pipeline_stage"), nullable=False)
    changed_by: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
