"""Service-layer tenant isolation tests.

Verifies that CRMService, UserService, PipelineService, and LeadService
correctly scope all operations through tenant-aware repositories.

The key insight: services themselves don't store tenant_id — they receive
tenant-scoped repos via DI constructor injection. So tenant isolation
is guaranteed by the DI factory → repo chain.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── CRM cross-tenant isolation ───────────────────────────────────────────


class TestCRMServiceTenantIsolation:
    """CRM operations cannot cross tenants."""

    def test_crm_service_repos_carry_tenant_id(self) -> None:
        """CRMService receives tenant-scoped lead_repo and pipeline_repo."""
        from infrastructure.di import get_crm_service

        svc = get_crm_service(MagicMock(), tenant_id=10)
        assert svc._leads._tenant_id == 10
        assert svc._pipeline._tenant_id == 10

    def test_crm_service_different_tenants_get_different_repos(self) -> None:
        """Two CRM services for different tenants have independent repos."""
        from infrastructure.di import get_crm_service

        svc_a = get_crm_service(MagicMock(), tenant_id=1)
        svc_b = get_crm_service(MagicMock(), tenant_id=2)

        assert svc_a._leads._tenant_id != svc_b._leads._tenant_id
        assert svc_a._pipeline._tenant_id != svc_b._pipeline._tenant_id

    def test_crm_service_none_tenant_is_unscoped(self) -> None:
        """CRM service with tenant_id=None is unscoped (backward compat)."""
        from infrastructure.di import get_crm_service

        svc = get_crm_service(MagicMock(), tenant_id=None)
        assert svc._leads._tenant_id is None
        assert svc._pipeline._tenant_id is None


# ── User queries are tenant-scoped ────────────────────────────────────────


class TestUserServiceTenantIsolation:
    """User queries are tenant-scoped."""

    def test_user_service_repo_carries_tenant_id(self) -> None:
        """UserService receives a tenant-scoped user_repo."""
        from infrastructure.di import get_user_service

        svc = get_user_service(MagicMock(), tenant_id=42)
        assert svc._repo._tenant_id == 42

    def test_user_service_different_tenants(self) -> None:
        """Two user services for different tenants use different scoping."""
        from infrastructure.di import get_user_service

        svc_a = get_user_service(MagicMock(), tenant_id=1)
        svc_b = get_user_service(MagicMock(), tenant_id=2)

        assert svc_a._repo._tenant_id == 1
        assert svc_b._repo._tenant_id == 2

    def test_user_repo_apply_tenant_filter(self) -> None:
        """User repo adds WHERE tenant_id = N when scoped."""
        from infrastructure.di import get_user_repo

        repo = get_user_repo(MagicMock(), tenant_id=7)
        # Verify _apply_tenant_filter adds the clause
        mock_stmt = MagicMock()
        from infrastructure.database.models.user import UserModel

        result = repo._apply_tenant_filter(mock_stmt, UserModel)
        mock_stmt.where.assert_called_once()

    def test_user_repo_no_filter_when_none(self) -> None:
        """User repo does NOT filter when tenant_id is None."""
        from infrastructure.di import get_user_repo

        repo = get_user_repo(MagicMock(), tenant_id=None)
        mock_stmt = MagicMock()
        from infrastructure.database.models.user import UserModel

        result = repo._apply_tenant_filter(mock_stmt, UserModel)
        mock_stmt.where.assert_not_called()
        assert result is mock_stmt


# ── Pipeline stage transitions are tenant-safe ───────────────────────────


class TestPipelineServiceTenantIsolation:
    """Pipeline stage transitions are tenant-safe."""

    def test_pipeline_service_all_repos_tenant_scoped(self) -> None:
        """PipelineService gets all 4 repos with correct tenant_id."""
        from infrastructure.di import get_pipeline_service

        svc = get_pipeline_service(MagicMock(), tenant_id=99)
        assert svc._leads._tenant_id == 99
        assert svc._pipeline._tenant_id == 99
        assert svc._actions._tenant_id == 99
        assert svc._audit._tenant_id == 99

    def test_pipeline_service_different_tenants(self) -> None:
        """Pipeline services for different tenants are fully independent."""
        from infrastructure.di import get_pipeline_service

        svc_a = get_pipeline_service(MagicMock(), tenant_id=10)
        svc_b = get_pipeline_service(MagicMock(), tenant_id=20)

        assert svc_a._leads._tenant_id == 10
        assert svc_b._leads._tenant_id == 20
        assert svc_a._pipeline._tenant_id == 10
        assert svc_b._pipeline._tenant_id == 20


# ── Lead service tenant isolation ─────────────────────────────────────────


class TestLeadServiceTenantIsolation:
    """Lead service correctly scopes through DI injection."""

    def test_lead_service_all_repos_tenant_scoped(self) -> None:
        """LeadService gets lead_repo, pipeline_repo, action_repo with tenant_id."""
        from infrastructure.di import get_lead_service

        svc = get_lead_service(MagicMock(), tenant_id=55)
        assert svc._leads._tenant_id == 55
        assert svc._pipeline._tenant_id == 55
        assert svc._actions._tenant_id == 55

    def test_lead_service_different_tenants(self) -> None:
        from infrastructure.di import get_lead_service

        svc_a = get_lead_service(MagicMock(), tenant_id=1)
        svc_b = get_lead_service(MagicMock(), tenant_id=2)

        assert svc_a._leads._tenant_id != svc_b._leads._tenant_id


# ── TenantScopedRepository mixin behavior ─────────────────────────────────


class TestTenantScopedRepositoryMixin:
    """Verify the shared mixin that all repos inherit."""

    def test_stamp_tenant_id_sets_value(self) -> None:
        from infrastructure.database.repositories.tenant_scope import TenantScopedRepository

        repo = TenantScopedRepository(MagicMock(), tenant_id=42)
        model = MagicMock()
        model.tenant_id = None
        repo._stamp_tenant_id(model)
        assert model.tenant_id == 42

    def test_stamp_tenant_id_noop_when_already_set(self) -> None:
        from infrastructure.database.repositories.tenant_scope import TenantScopedRepository

        repo = TenantScopedRepository(MagicMock(), tenant_id=42)
        model = MagicMock()
        model.tenant_id = 99  # already set
        repo._stamp_tenant_id(model)
        assert model.tenant_id == 99  # unchanged

    def test_stamp_tenant_id_noop_when_none_scope(self) -> None:
        from infrastructure.database.repositories.tenant_scope import TenantScopedRepository

        repo = TenantScopedRepository(MagicMock(), tenant_id=None)
        model = MagicMock()
        model.tenant_id = None
        repo._stamp_tenant_id(model)
        assert model.tenant_id is None

    def test_resolve_tenant_id_override(self) -> None:
        from infrastructure.database.repositories.tenant_scope import TenantScopedRepository

        repo = TenantScopedRepository(MagicMock(), tenant_id=42)
        assert repo._resolve_tenant_id(override=99) == 99

    def test_resolve_tenant_id_fallback(self) -> None:
        from infrastructure.database.repositories.tenant_scope import TenantScopedRepository

        repo = TenantScopedRepository(MagicMock(), tenant_id=42)
        assert repo._resolve_tenant_id() == 42


# ── DI factory chain completeness ────────────────────────────────────────


class TestDIFactoryChainCompleteness:
    """Every DI factory that accepts tenant_id correctly forwards it."""

    @pytest.mark.parametrize("factory_name,tenant_id,check_path", [
        ("get_lead_repo", 10, ["_tenant_id"]),
        ("get_user_repo", 20, ["_tenant_id"]),
        ("get_pipeline_repo", 30, ["_tenant_id"]),
        ("get_lead_service", 40, ["_leads._tenant_id"]),
        ("get_user_service", 50, ["_repo._tenant_id"]),
        ("get_crm_service", 60, ["_leads._tenant_id", "_pipeline._tenant_id"]),
        ("get_payment_service", 70, ["_repo._tenant_id"]),
        ("get_warranty_service", 80, ["_repo._tenant_id"]),
        ("get_group_settings_service", 90, ["_repo._tenant_id"]),
        ("get_admin_group_service", 100, ["_repo._tenant_id"]),
        ("get_broadcast_service", 110, ["_repo._tenant_id"]),
        ("get_lead_action_repo", 120, ["_tenant_id"]),
        ("get_pipeline_service", 130, ["_leads._tenant_id", "_pipeline._tenant_id"]),
        ("get_stats_service", 140, ["_join_repo._tenant_id"]),
        ("get_audit_log_repo", 150, ["_tenant_id"]),
        ("get_blocked_chat_repo", 160, ["_tenant_id"]),
        ("get_group_join_repo", 170, ["_tenant_id"]),
        ("get_subscription_payment_repo", 180, ["_tenant_id"]),
        ("get_ai_knowledge_repo", 190, ["_tenant_id"]),
        ("get_subscription_billing_service", 200, ["_payment_repo._tenant_id"]),
        ("get_lead_analytics_service", 210, ["_actions._tenant_id"]),
    ])
    def test_factory_forwards_tenant_id(
        self, factory_name: str, tenant_id: int, check_path: list[str],
    ) -> None:
        """Parametrized: every DI factory propagates tenant_id correctly."""
        import infrastructure.di as di

        factory = getattr(di, factory_name)
        obj = factory(MagicMock(), tenant_id=tenant_id)

        for path in check_path:
            target = obj
            for attr in path.split("."):
                target = getattr(target, attr)
            assert target == tenant_id, (
                f"{factory_name}(tenant_id={tenant_id}): "
                f"{path} = {target}, expected {tenant_id}"
            )


# ── Intentionally-global services ─────────────────────────────────────────


class TestIntentionallyGlobalServices:
    """Verify that global services don't accept tenant_id (by design)."""

    def test_get_tenant_service_is_global(self) -> None:
        """TenantService manages all tenants — no tenant scoping."""
        from infrastructure.di import get_tenant_service
        import inspect

        sig = inspect.signature(get_tenant_service)
        assert "tenant_id" not in sig.parameters

    def test_get_billing_service_is_global(self) -> None:
        """BillingService manages all billing — no tenant scoping."""
        from infrastructure.di import get_billing_service
        import inspect

        sig = inspect.signature(get_billing_service)
        assert "tenant_id" not in sig.parameters

    def test_get_tenant_bot_service_is_global(self) -> None:
        """TenantBotService manages all bot connections — no tenant scoping."""
        from infrastructure.di import get_tenant_bot_service
        import inspect

        sig = inspect.signature(get_tenant_bot_service)
        assert "tenant_id" not in sig.parameters
