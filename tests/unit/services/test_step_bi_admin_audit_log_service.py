"""Tests for Step BI — AdminAuditLogService."""
from __future__ import annotations
from core.services.admin_audit_log_service import AdminAuditLogService

svc = AdminAuditLogService


class TestValidAction:
    def test_known_actions(self):
        assert svc.is_valid_action("admin_user.create")
        assert svc.is_valid_action("rbac.denied")
        assert svc.is_valid_action("crm.reply.send")
        assert svc.is_valid_action("settings.mutate")

    def test_unknown_action(self):
        assert not svc.is_valid_action("admin.hack")
        assert not svc.is_valid_action("")


class TestValidStatus:
    def test_known(self):
        assert svc.is_valid_status("success")
        assert svc.is_valid_status("denied")
        assert svc.is_valid_status("failed")
        assert svc.is_valid_status("warning")

    def test_unknown(self):
        assert not svc.is_valid_status("error")
        assert not svc.is_valid_status("")


class TestGetValidActions:
    def test_returns_tuple(self):
        actions = svc.get_valid_actions()
        assert isinstance(actions, tuple)
        assert len(actions) > 15

    def test_contains_key_actions(self):
        actions = svc.get_valid_actions()
        assert "admin_user.create" in actions
        assert "rbac.denied" in actions
        assert "system.audit_view" in actions


class TestGetValidStatuses:
    def test_returns_tuple(self):
        statuses = svc.get_valid_statuses()
        assert isinstance(statuses, tuple)
        assert len(statuses) == 4


class TestSanitizeMetadata:
    def test_none(self):
        assert svc.sanitize_metadata(None) is None

    def test_clean(self):
        d = svc.sanitize_metadata({"key": "value"})
        assert d == {"key": "value"}

    def test_token_redacted(self):
        d = svc.sanitize_metadata({"token": "sk-secret123"})
        assert "[REDACTED]" in d["token"]

    def test_bot_token_redacted(self):
        d = svc.sanitize_metadata({"t": "1234567890:ABCdefGhIjKlMnOpQrStUvWxYz12345678"})
        assert "[REDACTED]" in d["t"]

    def test_phone_redacted(self):
        d = svc.sanitize_metadata({"phone": "+998901234567"})
        assert "[PHONE_REDACTED]" in d["phone"]

    def test_non_string_preserved(self):
        d = svc.sanitize_metadata({"count": 42, "active": True})
        assert d == {"count": 42, "active": True}


class TestSanitizeReason:
    def test_empty(self):
        assert svc.sanitize_reason("") == ""

    def test_clean(self):
        assert svc.sanitize_reason("Access denied") == "Access denied"

    def test_token_redacted(self):
        r = svc.sanitize_reason("Error with sk-secret123")
        assert "sk-" not in r

    def test_truncated(self):
        assert len(svc.sanitize_reason("x" * 1000)) <= 500


class TestBuildEntry:
    def test_basic(self):
        e = svc.build_entry(
            actor_admin_id="user1",
            actor_role="admin",
            action="admin_user.create",
            target_type="admin_user",
            target_id="user2",
        )
        assert e["actor_admin_id"] == "user1"
        assert e["action"] == "admin_user.create"
        assert e["status"] == "success"
        assert e["created_at"] != ""

    def test_invalid_status_defaults(self):
        e = svc.build_entry(status="hack")
        assert e["status"] == "success"

    def test_long_fields_truncated(self):
        e = svc.build_entry(
            actor_admin_id="x" * 200,
            action="y" * 200,
        )
        assert len(e["actor_admin_id"]) <= 100
        assert len(e["action"]) <= 80

    def test_metadata_sanitized(self):
        e = svc.build_entry(metadata={"token": "sk-secret123"})
        assert "[REDACTED]" in e["metadata_json"]["token"]


class TestBuildDenialEntry:
    def test_denial(self):
        e = svc.build_denial_entry(
            actor_admin_id="op1",
            actor_role="operator",
            action="settings.mutate",
            reason="insufficient permissions",
        )
        assert e["status"] == "denied"
        assert e["action"] == "settings.mutate"
        assert "insufficient" in e["reason"]

    def test_denial_target(self):
        e = svc.build_denial_entry(
            actor_admin_id="op1",
            actor_role="operator",
            action="rbac.denied",
            reason="no access",
            target_type="setting",
            target_id="agent_enabled",
        )
        assert e["target_type"] == "setting"
        assert e["target_id"] == "agent_enabled"


class TestBuildFailureEntry:
    def test_failure(self):
        e = svc.build_failure_entry(
            actor_admin_id="adm1",
            actor_role="admin",
            action="crm.reply.send",
            reason="telegram API error",
        )
        assert e["status"] == "failed"
        assert "telegram" in e["reason"]

    def test_failure_with_metadata(self):
        e = svc.build_failure_entry(
            actor_admin_id="adm1",
            actor_role="admin",
            action="crm.reply.send",
            reason="error",
            metadata={"error_code": 403},
        )
        assert e["metadata_json"]["error_code"] == 403


class TestRedactError:
    def test_token(self):
        assert "sk-" not in svc.redact_error("sk-secret123 failed")

    def test_bot_token(self):
        r = svc.redact_error("1234567890:ABCdefGhIjKlMnOpQrStUvWxYz12345678")
        assert "ABCdef" not in r

    def test_truncated(self):
        assert len(svc.redact_error("x" * 1000)) <= 500


class TestFormatForDisplay:
    def test_clean(self):
        e = {"action": "test", "reason": "ok"}
        d = svc.format_for_display(e)
        assert d["reason"] == "ok"

    def test_sanitizes_metadata(self):
        e = {"metadata_json": {"t": "sk-secret"}}
        d = svc.format_for_display(e)
        assert "[REDACTED]" in d["metadata_json"]["t"]

    def test_sanitizes_reason(self):
        e = {"reason": "sk-secret error", "metadata_json": None}
        d = svc.format_for_display(e)
        assert "sk-" not in d["reason"]


class TestImmutability:
    def test_entry_result_frozen(self):
        import pytest
        from core.services.admin_audit_log_service import AuditEntryResult
        r = AuditEntryResult(ok=True)
        with pytest.raises(AttributeError):
            r.ok = False  # type: ignore[misc]
