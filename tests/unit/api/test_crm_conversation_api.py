"""Tests for the CRM Conversation Inbox + Operator Send API.

Source-assertion + smoke style (matches the repo's API test convention).
"""

from __future__ import annotations

from pathlib import Path

_SRC = "apps/api/routes/admin_crm_conversations.py"


def _src() -> str:
    return Path(_SRC).read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.api.routes import admin_crm_conversations

        assert admin_crm_conversations is not None

    def test_router(self):
        from apps.api.routes.admin_crm_conversations import router

        assert router.prefix == "/api/v1/admin/crm/conversations"

    def test_registered_in_main(self):
        assert "admin_crm_conversations" in Path("apps/api/main.py").read_text(encoding="utf-8")

    def test_routes_on_app(self):
        from apps.api.main import app

        paths = [getattr(r, "path", "") for r in app.routes]
        assert "/api/v1/admin/crm/conversations" in paths
        assert "/api/v1/admin/crm/conversations/{contact_id}/messages" in paths
        assert "/api/v1/admin/crm/conversations/{contact_id}/operator-reply" in paths


class TestListEndpoint:
    def test_list_get(self):
        assert '@router.get("")' in _src()

    def test_filter_q(self):
        assert "q:" in _src()

    def test_filter_status(self):
        assert "status" in _src()

    def test_limit(self):
        assert "limit" in _src()

    def test_limit_max_100(self):
        assert "le=100" in _src()

    def test_offset(self):
        assert "offset" in _src()

    def test_returns_preview(self):
        assert "last_message_preview" in _src()

    def test_returns_masked_phone(self):
        assert "phone_masked" in _src() and "mask_phone" in _src()

    def test_orders_newest_first(self):
        assert "last_message_at.desc()" in _src()


class TestMessagesEndpoint:
    def test_messages_get(self):
        assert "/{contact_id}/messages" in _src()

    def test_chronological(self):
        assert "reversed" in _src()

    def test_returns_direction_sender(self):
        s = _src()
        assert '"direction"' in s and '"sender_type"' in s

    def test_uses_redacted_text(self):
        assert "redacted_text" in _src()


class TestOperatorReplyEndpoint:
    def test_post(self):
        assert '@router.post("/{contact_id}/operator-reply")' in _src()

    def test_calls_send_service(self):
        assert "send_operator_reply" in _src()

    def test_reads_enabled_flag(self):
        assert "operator_web_send_enabled" in _src()

    def test_disabled_returns_403(self):
        s = _src()
        assert "sender_disabled" in s and "403" in s

    def test_blocked_returns_422(self):
        assert "422" in _src()

    def test_confirm_required_409(self):
        s = _src()
        assert "confirm_required" in s and "409" in s

    def test_contact_not_found_404(self):
        assert "404" in _src() and "contact_not_found" in _src()

    def test_reads_confirm_send(self):
        assert "confirm_send" in _src()

    def test_passes_max_chars(self):
        assert "operator_web_send_max_chars" in _src()


class TestAuth:
    def test_auth_dependency(self):
        assert "require_api_token" in _src()

    def test_auth_on_router(self):
        assert "dependencies=[Depends(require_api_token)]" in _src()


class TestSafety:
    def test_single_send_path(self):
        # Exactly one send orchestration call — no second/bulk path.
        assert _src().count("send_operator_reply(") == 1

    def test_no_recipient_list(self):
        s = _src().lower()
        assert "recipients" not in s
        assert "chat_ids" not in s

    def test_no_broadcast_or_campaign_import(self):
        s = _src()
        assert "broadcast" not in s.lower()
        assert "campaign_send" not in s.lower()

    def test_no_ai_autosend(self):
        s = _src().lower()
        assert "auto_send" not in s
        assert "_call_ai" not in _src()

    def test_no_secret_literal(self):
        assert "sk-" not in _src()

    def test_no_raw_token_print(self):
        assert "print(" not in _src()


class TestFlagDefault:
    def test_send_flag_default_off(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings().operator_web_send_enabled is False


class TestSmoke:
    def test_api_app(self):
        from apps.api.main import app

        assert app is not None

    def test_models_import(self):
        from infrastructure.database.models.crm_contact import CRMContactModel
        from infrastructure.database.models.crm_message import CRMMessageModel

        assert CRMContactModel.__tablename__ == "crm_contacts"
        assert CRMMessageModel.__tablename__ == "crm_messages"

    def test_audit_model_import(self):
        from infrastructure.database.models.crm_operator_outbound_audit import (
            CRMOperatorOutboundAuditModel,
        )

        assert CRMOperatorOutboundAuditModel.__tablename__ == "crm_operator_outbound_audit"
