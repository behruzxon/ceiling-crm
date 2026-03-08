"""AI Knowledge repository interface."""
from __future__ import annotations

from abc import abstractmethod

from core.domain.ai_knowledge import AiKnowledge


class AbstractAiKnowledgeRepository:
    """Contract for tenant AI knowledge persistence."""

    @abstractmethod
    async def get_by_tenant(self, tenant_id: int) -> list[AiKnowledge]: ...

    @abstractmethod
    async def get_by_tenant_and_category(
        self, tenant_id: int, category: str,
    ) -> list[AiKnowledge]: ...

    @abstractmethod
    async def search_by_keywords(
        self, tenant_id: int, keywords: list[str], limit: int = 5,
    ) -> list[AiKnowledge]: ...

    @abstractmethod
    async def add_entry(
        self, tenant_id: int, category: str, title: str, content: str,
    ) -> AiKnowledge: ...

    @abstractmethod
    async def update_entry(self, entry_id: int, **fields: str) -> AiKnowledge | None: ...

    @abstractmethod
    async def delete_entry(self, entry_id: int) -> bool: ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: int) -> int: ...
