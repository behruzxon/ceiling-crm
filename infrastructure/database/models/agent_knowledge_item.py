"""SQLAlchemy ORM model for agent_knowledge_items.

Admin-editable knowledge base item (FAQ / price / catalog / warranty / objection
/ service_area / process / other). Authored manually or promoted from an Unknown
Question. The bot does not read these yet — see doc 156.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class AgentKnowledgeItemModel(Base):
    __tablename__ = "agent_knowledge_items"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    question: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    answer: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    category: Mapped[str] = mapped_column(sa.String(30), nullable=False, server_default="faq")
    language: Mapped[str] = mapped_column(sa.String(8), nullable=False, server_default="uz")
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="draft")
    source: Mapped[str] = mapped_column(sa.String(30), nullable=False, server_default="manual")
    source_unknown_question_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    aliases_json: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    tags_json: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    priority: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="100")
    created_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    __table_args__ = (
        sa.Index("ix_kb_status", "status"),
        sa.Index("ix_kb_category", "category"),
        sa.Index("ix_kb_language", "language"),
        sa.Index("ix_kb_source_uq", "source_unknown_question_id"),
        sa.Index("ix_kb_created", "created_at"),
        sa.Index("ix_kb_priority", "priority"),
        sa.Index("ix_kb_status_category_lang", "status", "category", "language"),
    )
