"""Tests for Step AX — CRM Contact + Message services (pure logic)."""

from __future__ import annotations

from core.services.crm_contact_service import CRMContactService
from core.services.crm_message_service import CRMMessageService


class TestContactValidation:
    def test_valid_status(self):
        assert CRMContactService.is_valid_status("new")
        assert CRMContactService.is_valid_status("hot")
        assert CRMContactService.is_valid_status("won")
        assert CRMContactService.is_valid_status("lost")
        assert CRMContactService.is_valid_status("stopped")

    def test_invalid_status(self):
        assert not CRMContactService.is_valid_status("unknown")
        assert not CRMContactService.is_valid_status("")

    def test_all_statuses(self):
        for s in [
            "new",
            "active",
            "browsing",
            "price_interested",
            "hot",
            "operator_needed",
            "order_started",
            "won",
            "lost",
            "stopped",
        ]:
            assert CRMContactService.is_valid_status(s)


class TestContactRedaction:
    def test_phone(self):
        assert "+998901234567" not in CRMContactService.redact_text("Call +998901234567")

    def test_token(self):
        assert "sk-secret" not in CRMContactService.redact_text("sk-secret123")

    def test_clean(self):
        assert CRMContactService.redact_text("Salom") == "Salom"


class TestMessageRedaction:
    def test_phone(self):
        assert "+998" not in CRMMessageService.redact_text("+998901234567")

    def test_token(self):
        assert "sk-" not in CRMMessageService.redact_text("sk-abc123")

    def test_clean(self):
        assert CRMMessageService.redact_text("hello") == "hello"

    def test_bearer(self):
        assert "Bearer" not in CRMMessageService.redact_text("Bearer eyJtoken")


class TestModels:
    def test_contact_model(self):
        from infrastructure.database.models.crm_contact import CRMContactModel

        assert CRMContactModel.__tablename__ == "crm_contacts"

    def test_message_model(self):
        from infrastructure.database.models.crm_message import CRMMessageModel

        assert CRMMessageModel.__tablename__ == "crm_messages"

    def test_note_model(self):
        from infrastructure.database.models.crm_message import CRMContactNoteModel

        assert CRMContactNoteModel.__tablename__ == "crm_contact_notes"

    def test_tag_model(self):
        from infrastructure.database.models.crm_message import CRMContactTagModel

        assert CRMContactTagModel.__tablename__ == "crm_contact_tags"


class TestMigration:
    def test_importable(self):
        import importlib

        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1300_y0z1a2b3c4d5_add_crm_tables"
        )
        assert callable(mod.upgrade) and callable(mod.downgrade)


class TestDI:
    def test_contact_service(self):
        from infrastructure.di import get_crm_contact_service

        assert callable(get_crm_contact_service)

    def test_message_service(self):
        from infrastructure.di import get_crm_message_service

        assert callable(get_crm_message_service)
