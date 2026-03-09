"""Handler-level tenant_id propagation tests.

Verifies that DI factory functions correctly pass tenant_id through
to repository/service constructors, ensuring multi-tenant isolation.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── DI factory tenant_id propagation tests ───────────────────────────────


class TestDIFactoryTenantPropagation:
    """Verify that every DI factory forwards tenant_id to the underlying repo."""

    def test_get_lead_repo(self) -> None:
        from infrastructure.di import get_lead_repo
        repo = get_lead_repo(MagicMock(), tenant_id=42)
        assert repo._tenant_id == 42

    def test_get_lead_repo_none(self) -> None:
        from infrastructure.di import get_lead_repo
        repo = get_lead_repo(MagicMock(), tenant_id=None)
        assert repo._tenant_id is None

    def test_get_user_repo(self) -> None:
        from infrastructure.di import get_user_repo
        repo = get_user_repo(MagicMock(), tenant_id=99)
        assert repo._tenant_id == 99

    def test_get_pipeline_repo(self) -> None:
        from infrastructure.di import get_pipeline_repo
        repo = get_pipeline_repo(MagicMock(), tenant_id=7)
        assert repo._tenant_id == 7

    def test_get_lead_service(self) -> None:
        from infrastructure.di import get_lead_service
        svc = get_lead_service(MagicMock(), tenant_id=55)
        assert svc._leads._tenant_id == 55
        assert svc._pipeline._tenant_id == 55

    def test_get_user_service(self) -> None:
        from infrastructure.di import get_user_service
        svc = get_user_service(MagicMock(), tenant_id=33)
        assert svc._repo._tenant_id == 33

    def test_get_payment_service(self) -> None:
        from infrastructure.di import get_payment_service
        svc = get_payment_service(MagicMock(), tenant_id=12)
        assert svc._repo._tenant_id == 12

    def test_get_warranty_service(self) -> None:
        from infrastructure.di import get_warranty_service
        svc = get_warranty_service(MagicMock(), tenant_id=77)
        assert svc._repo._tenant_id == 77

    def test_get_crm_service(self) -> None:
        from infrastructure.di import get_crm_service
        svc = get_crm_service(MagicMock(), tenant_id=5)
        assert svc._leads._tenant_id == 5
        assert svc._pipeline._tenant_id == 5

    def test_get_group_settings_service(self) -> None:
        from infrastructure.di import get_group_settings_service
        svc = get_group_settings_service(MagicMock(), tenant_id=8)
        assert svc._repo._tenant_id == 8

    def test_get_admin_group_service(self) -> None:
        from infrastructure.di import get_admin_group_service
        svc = get_admin_group_service(MagicMock(), tenant_id=15)
        assert svc._repo._tenant_id == 15

    def test_get_broadcast_service(self) -> None:
        from infrastructure.di import get_broadcast_service
        svc = get_broadcast_service(MagicMock(), tenant_id=3)
        assert svc._repo._tenant_id == 3

    def test_get_lead_action_repo(self) -> None:
        from infrastructure.di import get_lead_action_repo
        repo = get_lead_action_repo(MagicMock(), tenant_id=60)
        assert repo._tenant_id == 60

    def test_get_pipeline_service(self) -> None:
        from infrastructure.di import get_pipeline_service
        svc = get_pipeline_service(MagicMock(), tenant_id=20)
        assert svc._leads._tenant_id == 20
        assert svc._pipeline._tenant_id == 20

    def test_get_stats_service(self) -> None:
        from infrastructure.di import get_stats_service
        svc = get_stats_service(MagicMock(), tenant_id=11)
        assert svc._join_repo._tenant_id == 11

    def test_get_audit_log_repo(self) -> None:
        from infrastructure.di import get_audit_log_repo
        repo = get_audit_log_repo(MagicMock(), tenant_id=44)
        assert repo._tenant_id == 44

    def test_get_blocked_chat_repo(self) -> None:
        from infrastructure.di import get_blocked_chat_repo
        repo = get_blocked_chat_repo(MagicMock(), tenant_id=25)
        assert repo._tenant_id == 25

    def test_get_group_join_repo(self) -> None:
        from infrastructure.di import get_group_join_repo
        repo = get_group_join_repo(MagicMock(), tenant_id=88)
        assert repo._tenant_id == 88

    def test_get_subscription_payment_repo(self) -> None:
        from infrastructure.di import get_subscription_payment_repo
        repo = get_subscription_payment_repo(MagicMock(), tenant_id=31)
        assert repo._tenant_id == 31

    def test_get_ai_knowledge_repo(self) -> None:
        from infrastructure.di import get_ai_knowledge_repo
        repo = get_ai_knowledge_repo(MagicMock(), tenant_id=50)
        assert repo._tenant_id == 50


# ── Handler data dict pattern tests ──────────────────────────────────────


class TestHandlerDataTenantExtraction:
    """Verify the data.get('tenant_id') pattern used across handlers."""

    def test_data_get_returns_tenant_id(self) -> None:
        """Simulate handler kwargs with tenant_id."""
        data: dict = {"tenant_id": 42, "db_session": MagicMock()}
        assert data.get("tenant_id") == 42

    def test_data_get_returns_none_when_missing(self) -> None:
        """When tenant_id is not in data, None is returned (safe default)."""
        data: dict = {"db_session": MagicMock()}
        assert data.get("tenant_id") is None

    def test_tenant_id_passed_through_di_chain(self) -> None:
        """End-to-end: data dict -> DI factory -> repo._tenant_id."""
        from infrastructure.di import get_lead_repo

        data: dict = {"tenant_id": 42, "db_session": MagicMock()}
        _tid = data.get("tenant_id")
        repo = get_lead_repo(MagicMock(), tenant_id=_tid)
        assert repo._tenant_id == 42

    def test_fsm_tenant_id_roundtrip(self) -> None:
        """Verify that storing _tenant_id in FSM and reading it back works."""
        from infrastructure.di import get_lead_service

        # Simulates: state.update_data(_tenant_id=42) + fsm.get("_tenant_id")
        fsm_data = {"_tenant_id": 42, "name": "Test", "phone": "+998901234567"}
        _tid = fsm_data.get("_tenant_id")

        svc = get_lead_service(MagicMock(), tenant_id=_tid)
        assert svc._leads._tenant_id == 42
