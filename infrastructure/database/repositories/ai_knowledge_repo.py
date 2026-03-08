"""PostgreSQL implementation of AbstractAiKnowledgeRepository."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.ai_knowledge import AiKnowledge
from core.repositories.ai_knowledge_repo import AbstractAiKnowledgeRepository
from infrastructure.database.models.ai_knowledge import TenantAiKnowledgeModel


class PostgresAiKnowledgeRepository(AbstractAiKnowledgeRepository):
    """Concrete SQLAlchemy/PostgreSQL AI knowledge repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Mapping ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_domain(model: TenantAiKnowledgeModel) -> AiKnowledge:
        return AiKnowledge(
            id=model.id,
            tenant_id=model.tenant_id,
            category=model.category,
            title=model.title,
            content=model.content,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # ── Reads ─────────────────────────────────────────────────────────────

    async def get_by_tenant(self, tenant_id: int) -> list[AiKnowledge]:
        stmt = (
            sa.select(TenantAiKnowledgeModel)
            .where(TenantAiKnowledgeModel.tenant_id == tenant_id)
            .order_by(TenantAiKnowledgeModel.category, TenantAiKnowledgeModel.title)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_by_tenant_and_category(
        self, tenant_id: int, category: str,
    ) -> list[AiKnowledge]:
        stmt = (
            sa.select(TenantAiKnowledgeModel)
            .where(
                TenantAiKnowledgeModel.tenant_id == tenant_id,
                TenantAiKnowledgeModel.category == category,
            )
            .order_by(TenantAiKnowledgeModel.title)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def search_by_keywords(
        self, tenant_id: int, keywords: list[str], limit: int = 5,
    ) -> list[AiKnowledge]:
        """Search knowledge entries by keyword match in title or content.

        Uses ILIKE for each keyword (OR logic) — returns entries matching
        at least one keyword, ordered by number of matches descending.
        """
        if not keywords:
            return await self.get_by_tenant(tenant_id)

        # Build OR conditions for keyword matching
        conditions = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append(TenantAiKnowledgeModel.title.ilike(pattern))
            conditions.append(TenantAiKnowledgeModel.content.ilike(pattern))

        stmt = (
            sa.select(TenantAiKnowledgeModel)
            .where(
                TenantAiKnowledgeModel.tenant_id == tenant_id,
                sa.or_(*conditions),
            )
            .order_by(TenantAiKnowledgeModel.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_by_tenant(self, tenant_id: int) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(TenantAiKnowledgeModel)
            .where(TenantAiKnowledgeModel.tenant_id == tenant_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── Writes ────────────────────────────────────────────────────────────

    async def add_entry(
        self, tenant_id: int, category: str, title: str, content: str,
    ) -> AiKnowledge:
        model = TenantAiKnowledgeModel(
            tenant_id=tenant_id,
            category=category,
            title=title,
            content=content,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update_entry(self, entry_id: int, **fields: str) -> AiKnowledge | None:
        model = await self._session.get(TenantAiKnowledgeModel, entry_id)
        if model is None:
            return None
        for attr in ("category", "title", "content"):
            if attr in fields:
                setattr(model, attr, fields[attr])
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def delete_entry(self, entry_id: int) -> bool:
        stmt = sa.delete(TenantAiKnowledgeModel).where(
            TenantAiKnowledgeModel.id == entry_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
