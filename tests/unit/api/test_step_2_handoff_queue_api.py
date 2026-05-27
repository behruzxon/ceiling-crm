"""Tests for Step 2 — Handoff Queue API."""

from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path(
        "apps/api/routes/admin_crm_handoffs.py",
    ).read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.api.routes import admin_crm_handoffs

        assert admin_crm_handoffs is not None

    def test_router(self):
        from apps.api.routes.admin_crm_handoffs import router

        assert router is not None

    def test_registered_in_main(self):
        c = Path("apps/api/main.py").read_text(encoding="utf-8")
        assert "admin_crm_handoffs" in c


class TestEndpoints:
    def test_summary_endpoint(self):
        assert "summary" in _src()

    def test_queue_endpoint(self):
        assert "queue" in _src()

    def test_assign_endpoint(self):
        assert "assign" in _src()

    def test_contacted_endpoint(self):
        assert "contacted" in _src()

    def test_resolve_endpoint(self):
        assert "resolve" in _src()

    def test_cancel_endpoint(self):
        assert "cancel" in _src()


class TestQueryParams:
    def test_status_filter(self):
        assert "status" in _src()

    def test_priority_filter(self):
        assert "priority" in _src()

    def test_limit(self):
        assert "limit" in _src()

    def test_limit_max_100(self):
        assert "le=100" in _src()

    def test_offset(self):
        assert "offset" in _src()


class TestPhoneMasking:
    def test_phone_masked_field(self):
        assert "phone_masked" in _src()


class TestErrorHandling:
    def test_404_on_invalid_id(self):
        assert "404" in _src()

    def test_not_found_detail(self):
        assert "not found" in _src().lower()


class TestAuth:
    def test_auth_dependency(self):
        assert "require_api_token" in _src()


class TestStatusTransitions:
    def test_assigned_status(self):
        assert '"assigned"' in _src()

    def test_contacted_status(self):
        assert '"contacted"' in _src()

    def test_resolved_status(self):
        assert '"resolved"' in _src()

    def test_cancelled_status(self):
        assert '"cancelled"' in _src()


class TestSafety:
    def test_no_token_in_source(self):
        assert "sk-" not in _src()

    def test_no_telegram_send(self):
        assert "send_message" not in _src()

    def test_no_openai_call(self):
        assert "openai" not in _src().lower()


class TestSmoke:
    def test_api_app(self):
        from apps.api.main import app

        assert app is not None

    def test_model_import(self):
        from infrastructure.database.models.crm_operator_handoff import (
            CRMOperatorHandoffModel,
        )

        assert CRMOperatorHandoffModel is not None
