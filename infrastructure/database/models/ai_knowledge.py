"""SQLAlchemy ORM model for tenant AI knowledge base entries.

Each tenant can define structured knowledge entries that get injected
into the AI system prompt, so the bot answers with tenant-specific
business information (services, prices, policies, FAQ, etc.).
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class TenantAiKnowledgeModel(Base):
    __tablename__ = "tenant_ai_knowledge"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_tenant_ai_knowledge_tenant_id", "tenant_id"),
        sa.Index("ix_tenant_ai_knowledge_category", "tenant_id", "category"),
    )
