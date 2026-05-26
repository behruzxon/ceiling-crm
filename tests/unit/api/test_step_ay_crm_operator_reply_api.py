"""Tests for Step AY — Operator Reply API."""
from __future__ import annotations

class TestEndpoints:
    def test_preview_exists(self):
        from apps.api.main import create_app
        paths = [r.path for r in create_app().routes]
        assert any("reply/preview" in p for p in paths)

    def test_send_exists(self):
        from apps.api.main import create_app
        paths = [r.path for r in create_app().routes]
        assert any("reply/send" in p for p in paths)

    def test_auth(self):
        from apps.api.routes.admin_crm import router
        assert len(router.dependencies) > 0

class TestNonRegression:
    def test_contacts_exists(self):
        from apps.api.main import create_app
        assert any("/crm/contacts" in r.path for r in create_app().routes)

    def test_signal(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
