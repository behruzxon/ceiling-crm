"""Tests for Step AX — CRM API endpoints."""

from __future__ import annotations


class TestEndpoints:
    def test_contacts_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("/crm/contacts" in p for p in paths)

    def test_detail_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("contact_id" in p and "crm" in p for p in paths)

    def test_messages_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("messages" in p and "crm" in p for p in paths)

    def test_notes_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("notes" in p for p in paths)

    def test_tags_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("tags" in p for p in paths)

    def test_auth(self):
        from apps.api.routes.admin_crm import router

        assert len(router.dependencies) > 0

    def test_prefix(self):
        from apps.api.routes.admin_crm import router

        assert "crm" in router.prefix


class TestNonRegression:
    def test_agent_metrics(self):
        from apps.api.main import create_app

        assert any("metrics/overview" in r.path for r in create_app().routes)

    def test_signal(self):
        from core.services.lead_signal_service import LeadSignalService

        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
