"""Cross-tenant isolation tests.

Verifies that repositories properly isolate data between tenants:
  1. AI Knowledge — update/delete cannot cross tenants
  2. Subscription Payment — lookup/update cannot cross tenants
  3. TenantScopedRepository mixin — _apply_tenant_filter, _resolve_tenant_id
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa

from infrastructure.database.repositories.tenant_scope import TenantScopedRepository


# ── TenantScopedRepository mixin unit tests ────────────────────────────────


class TestTenantScopedMixin:
    """Verify the core mixin methods."""

    def test_apply_tenant_filter_with_tenant_id(self) -> None:
        """When tenant_id is set, WHERE clause is appended."""
        repo = TenantScopedRepository(session=MagicMock(), tenant_id=42)

        model = MagicMock()
        model.tenant_id = MagicMock()

        base_stmt = MagicMock()
        result = repo._apply_tenant_filter(base_stmt, model)

        base_stmt.where.assert_called_once()
        assert result == base_stmt.where.return_value

    def test_apply_tenant_filter_without_tenant_id(self) -> None:
        """When tenant_id is None, statement is returned unchanged."""
        repo = TenantScopedRepository(session=MagicMock(), tenant_id=None)

        model = MagicMock()
        base_stmt = MagicMock()
        result = repo._apply_tenant_filter(base_stmt, model)

        base_stmt.where.assert_not_called()
        assert result is base_stmt

    def test_resolve_tenant_id_prefers_override(self) -> None:
        """Explicit override takes priority over constructor value."""
        repo = TenantScopedRepository(session=MagicMock(), tenant_id=10)
        assert repo._resolve_tenant_id(99) == 99

    def test_resolve_tenant_id_falls_back(self) -> None:
        """Without override, returns constructor value."""
        repo = TenantScopedRepository(session=MagicMock(), tenant_id=10)
        assert repo._resolve_tenant_id() == 10

    def test_stamp_tenant_id_sets_when_none(self) -> None:
        """_stamp_tenant_id sets model.tenant_id when it's None."""
        repo = TenantScopedRepository(session=MagicMock(), tenant_id=42)
        model = MagicMock(tenant_id=None)
        repo._stamp_tenant_id(model)
        assert model.tenant_id == 42

    def test_stamp_tenant_id_no_overwrite(self) -> None:
        """_stamp_tenant_id does NOT overwrite existing tenant_id."""
        repo = TenantScopedRepository(session=MagicMock(), tenant_id=42)
        model = MagicMock(tenant_id=99)
        repo._stamp_tenant_id(model)
        assert model.tenant_id == 99


# ── AI Knowledge repo isolation tests ──────────────────────────────────────


class TestAiKnowledgeRepoIsolation:
    """Verify ai_knowledge_repo tenant isolation."""

    def _make_mock_model(self, entry_id: int = 1, tenant_id: int = 10):
        m = MagicMock()
        m.id = entry_id
        m.tenant_id = tenant_id
        m.category = "faq"
        m.title = "Test"
        m.content = "Content"
        m.created_at = datetime.now(tz=timezone.utc)
        m.updated_at = datetime.now(tz=timezone.utc)
        return m

    async def test_update_entry_blocks_cross_tenant(self) -> None:
        """Tenant B (id=20) cannot update Tenant A's (id=10) entry."""
        from infrastructure.database.repositories.ai_knowledge_repo import (
            PostgresAiKnowledgeRepository,
        )

        session = AsyncMock()
        model = self._make_mock_model(entry_id=1, tenant_id=10)
        session.get = AsyncMock(return_value=model)

        # Repo scoped to tenant 20 (different from entry's tenant 10)
        repo = PostgresAiKnowledgeRepository(session, tenant_id=20)
        result = await repo.update_entry(1, title="Hacked")

        # Should return None — entry belongs to tenant 10, not 20
        assert result is None

    async def test_update_entry_allows_same_tenant(self) -> None:
        """Tenant A (id=10) CAN update their own entry."""
        from infrastructure.database.repositories.ai_knowledge_repo import (
            PostgresAiKnowledgeRepository,
        )

        session = AsyncMock()
        model = self._make_mock_model(entry_id=1, tenant_id=10)
        session.get = AsyncMock(return_value=model)
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = PostgresAiKnowledgeRepository(session, tenant_id=10)
        result = await repo.update_entry(1, title="Updated")

        assert result is not None

    async def test_delete_entry_blocks_cross_tenant(self) -> None:
        """Tenant B cannot delete Tenant A's entry."""
        from infrastructure.database.repositories.ai_knowledge_repo import (
            PostgresAiKnowledgeRepository,
        )

        session = AsyncMock()
        # Mock execute result with rowcount=0 (no rows matched WHERE tenant_id=20)
        exec_result = MagicMock()
        exec_result.rowcount = 0
        session.execute = AsyncMock(return_value=exec_result)

        repo = PostgresAiKnowledgeRepository(session, tenant_id=20)
        result = await repo.delete_entry(1)

        # Should return False — no rows deleted (entry belongs to tenant 10)
        assert result is False

        # Verify the WHERE clause includes tenant_id
        call_args = session.execute.call_args[0][0]
        compiled = call_args.compile(
            compile_kwargs={"literal_binds": True},
        )
        sql_str = str(compiled)
        assert "tenant_id" in sql_str

    async def test_add_entry_asserts_tenant_id(self) -> None:
        """add_entry asserts tenant_id is not None."""
        from infrastructure.database.repositories.ai_knowledge_repo import (
            PostgresAiKnowledgeRepository,
        )

        session = AsyncMock()
        # Repo with no tenant_id and no explicit param
        repo = PostgresAiKnowledgeRepository(session, tenant_id=None)

        with pytest.raises(AssertionError, match="tenant_id required"):
            await repo.add_entry(
                tenant_id=None,  # type: ignore[arg-type]
                category="faq",
                title="Test",
                content="Content",
            )


# ── Subscription Payment repo isolation tests ─────────────────────────────


class TestSubscriptionPaymentRepoIsolation:
    """Verify subscription_payment_repo tenant isolation."""

    def _make_mock_model(self, payment_id: int = 1, tenant_id: int = 10):
        m = MagicMock()
        m.id = payment_id
        m.tenant_id = tenant_id
        m.provider = "click"
        m.status = "pending"
        m.amount = 100_000
        m.currency = "UZS"
        m.description = "Test"
        m.merchant_trans_id = "sub_10_123_abc"
        m.provider_trans_id = None
        m.extension_days = 30
        m.paid_at = None
        m.canceled_at = None
        m.created_at = datetime.now(tz=timezone.utc)
        m.updated_at = datetime.now(tz=timezone.utc)
        m.provider_meta = {}
        return m

    async def test_get_by_id_blocks_cross_tenant(self) -> None:
        """Tenant B cannot read Tenant A's payment by ID."""
        from infrastructure.database.repositories.subscription_payment_repo import (
            PostgresSubscriptionPaymentRepository,
        )

        session = AsyncMock()
        model = self._make_mock_model(payment_id=1, tenant_id=10)
        session.get = AsyncMock(return_value=model)

        repo = PostgresSubscriptionPaymentRepository(session, tenant_id=20)
        result = await repo.get_by_id(1)

        assert result is None

    async def test_get_by_id_allows_same_tenant(self) -> None:
        """Tenant A CAN read their own payment."""
        from infrastructure.database.repositories.subscription_payment_repo import (
            PostgresSubscriptionPaymentRepository,
        )

        session = AsyncMock()
        model = self._make_mock_model(payment_id=1, tenant_id=10)
        session.get = AsyncMock(return_value=model)

        repo = PostgresSubscriptionPaymentRepository(session, tenant_id=10)
        result = await repo.get_by_id(1)

        assert result is not None
        assert result.tenant_id == 10

    async def test_update_status_blocks_cross_tenant(self) -> None:
        """Tenant B cannot update Tenant A's payment status."""
        from infrastructure.database.repositories.subscription_payment_repo import (
            PostgresSubscriptionPaymentRepository,
        )
        from shared.constants.enums import SubscriptionPaymentStatus

        session = AsyncMock()
        model = self._make_mock_model(payment_id=1, tenant_id=10)
        session.get = AsyncMock(return_value=model)

        repo = PostgresSubscriptionPaymentRepository(session, tenant_id=20)

        with pytest.raises(ValueError, match="not found"):
            await repo.update_status(1, SubscriptionPaymentStatus.PAID)

    async def test_delete_blocks_cross_tenant(self) -> None:
        """Tenant B cannot delete Tenant A's payment."""
        from infrastructure.database.repositories.subscription_payment_repo import (
            PostgresSubscriptionPaymentRepository,
        )

        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.rowcount = 0
        session.execute = AsyncMock(return_value=exec_result)

        repo = PostgresSubscriptionPaymentRepository(session, tenant_id=20)
        result = await repo.delete(1)

        assert result is False

    async def test_list_by_tenant_asserts_tenant_id(self) -> None:
        """list_by_tenant asserts tenant_id is not None."""
        from infrastructure.database.repositories.subscription_payment_repo import (
            PostgresSubscriptionPaymentRepository,
        )

        session = AsyncMock()
        repo = PostgresSubscriptionPaymentRepository(session, tenant_id=None)

        with pytest.raises(AssertionError, match="tenant_id required"):
            await repo.list_by_tenant(tenant_id=None, limit=10)  # type: ignore[arg-type]
