"""Tests for Step AY — CRMOperatorReplyService."""
from __future__ import annotations
from core.services.crm_operator_reply_service import CRMOperatorReplyService

svc = CRMOperatorReplyService
_CONTACT = {"telegram_user_id": 123, "telegram_chat_id": 123, "lead_status": "active", "temperature": "warm", "metadata_json": {}}

class TestPreviewBlockers:
    def test_disabled(self):
        r = svc.preview_reply(_CONTACT, "hi", enabled=False)
        assert not r.allowed and "operator_reply_disabled" in r.blockers

    def test_empty(self):
        r = svc.preview_reply(_CONTACT, "", enabled=True)
        assert "empty_text" in r.blockers

    def test_too_long(self):
        r = svc.preview_reply(_CONTACT, "x" * 1001, enabled=True, max_length=1000)
        assert any("too_long" in b for b in r.blockers)

    def test_missing_contact(self):
        r = svc.preview_reply(None, "hi", enabled=True)
        assert "contact_not_found" in r.blockers

    def test_missing_chat_id(self):
        r = svc.preview_reply({"telegram_user_id": None, "telegram_chat_id": None, "lead_status": "new", "temperature": None, "metadata_json": {}}, "hi", enabled=True)
        assert "missing_chat_id" in r.blockers

    def test_stopped(self):
        r = svc.preview_reply({**_CONTACT, "lead_status": "stopped"}, "hi", enabled=True)
        assert "contact_stopped" in r.blockers

    def test_lost(self):
        r = svc.preview_reply({**_CONTACT, "lead_status": "lost"}, "hi", enabled=True)
        assert "contact_lost" in r.blockers

    def test_followup_disabled(self):
        r = svc.preview_reply({**_CONTACT, "metadata_json": {"followup_disabled": True}}, "hi", enabled=True)
        assert "followup_disabled" in r.blockers

    def test_token(self):
        r = svc.preview_reply(_CONTACT, "sk-secret123abc", enabled=True)
        assert "token_pattern" in r.blockers

    def test_bot_token(self):
        r = svc.preview_reply(_CONTACT, "1234567890:AABBCCDDEEFFaabbccddeeffgghhiijj", enabled=True)
        assert "bot_token_pattern" in r.blockers

class TestPreviewWarnings:
    def test_cold(self):
        r = svc.preview_reply({**_CONTACT, "temperature": "cold"}, "hi", enabled=True)
        assert "cold_contact" in r.warnings

    def test_phone(self):
        r = svc.preview_reply(_CONTACT, "Call +998901234567", enabled=True)
        assert "contains_phone" in r.warnings

class TestPreviewAllowed:
    def test_valid(self):
        r = svc.preview_reply(_CONTACT, "Salom! Narx hisoblashga yordam beraman.", enabled=True)
        assert r.allowed is True

    def test_hash(self):
        r = svc.preview_reply(_CONTACT, "test", enabled=True)
        assert r.message_hash and len(r.message_hash) == 16

    def test_hash_stable(self):
        h1 = svc.build_message_hash("hello")
        h2 = svc.build_message_hash("hello")
        assert h1 == h2

    def test_preview_truncated(self):
        r = svc.preview_reply(_CONTACT, "x" * 200, enabled=True)
        assert len(r.sanitized_preview) <= 100

class TestRedaction:
    def test_token(self):
        assert "sk-" not in svc.redact_error("Error with sk-secret123")
    def test_bot_token(self):
        assert "1234567890:" not in svc.redact_error("1234567890:AABBCCDDEEFFaabbccddeeffgghhiijj")
    def test_truncate(self):
        assert len(svc.redact_error("x" * 1000)) <= 500

class TestModel:
    def test_importable(self):
        from infrastructure.database.models.crm_operator_outbound_audit import CRMOperatorOutboundAuditModel
        assert CRMOperatorOutboundAuditModel.__tablename__ == "crm_operator_outbound_audit"

class TestMigration:
    def test_importable(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1350_z1a2b3c4d5e6_add_crm_operator_outbound_audit"
        )
        assert callable(mod.upgrade)

class TestSettings:
    def test_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_operator_reply_enabled"].default is False
    def test_max_length(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_operator_reply_max_length"].default == 1000
    def test_block_stopped(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_operator_reply_block_stopped"].default is True

class TestImmutability:
    def test_frozen(self):
        import pytest
        r = svc.preview_reply(_CONTACT, "hi", enabled=True)
        with pytest.raises(AttributeError):
            r.allowed = False  # type: ignore[misc]
