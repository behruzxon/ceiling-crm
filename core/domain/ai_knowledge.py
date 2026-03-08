"""Domain model for tenant AI knowledge base entries."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AiKnowledge(BaseModel):
    """Frozen domain object for a single knowledge base entry."""

    model_config = {"frozen": True}

    id: int
    tenant_id: int
    category: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
