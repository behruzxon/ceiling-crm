"""Tests for Step BL — AdminSecurityActionService."""

from __future__ import annotations

from core.services.admin_security_action_service import AdminSecurityActionService

svc = AdminSecurityActionService


class TestCheckActionsEnabled:
    def test_disabled(self):
        r = svc.check_actions_enabled(False)
        assert not r.ok
        assert "disabled" in r.error

    def test_enabled(self):
        assert svc.check_actions_enabled(True).ok


class TestRequireConfirmation:
    def test_required_not_confirmed(self):
        r = svc.require_confirmation(False, require=True)
        assert not r.ok
        assert "confirmation" in r.error

    def test_required_confirmed(self):
        assert svc.require_confirmation(True, require=True).ok

    def test_not_required(self):
        assert svc.require_confirmation(False, require=False).ok


class TestPreventSelfLockout:
    def test_same_id(self):
        r = svc.prevent_self_lockout("u1", "u1")
        assert not r.ok
        assert "self" in r.error

    def test_different_id(self):
        assert svc.prevent_self_lockout("u1", "u2").ok

    def test_empty(self):
        assert svc.prevent_self_lockout("", "").ok


class TestPreventLastOwnerDisable:
    def test_super_owner(self):
        r = svc.prevent_last_owner_disable("owner", True, 2)
        assert not r.ok
        assert "super_owner" in r.error

    def test_last_owner(self):
        r = svc.prevent_last_owner_disable("owner", False, 1)
        assert not r.ok
        assert "last_owner" in r.error

    def test_not_last_owner(self):
        assert svc.prevent_last_owner_disable("owner", False, 2).ok

    def test_non_owner(self):
        assert svc.prevent_last_owner_disable("admin", False, 1).ok


class TestValidateRevokeSession:
    def test_disabled(self):
        r = svc.validate_revoke_session({"status": "active"}, actions_enabled=False)
        assert not r.ok
        assert "disabled" in r.error

    def test_no_confirm(self):
        r = svc.validate_revoke_session({"status": "active"}, confirm=False, actions_enabled=True)
        assert not r.ok
        assert "confirmation" in r.error

    def test_not_found(self):
        r = svc.validate_revoke_session(None, confirm=True, actions_enabled=True)
        assert not r.ok
        assert "not_found" in r.error

    def test_already_revoked(self):
        r = svc.validate_revoke_session({"status": "revoked"}, confirm=True, actions_enabled=True)
        assert not r.ok
        assert "already_revoked" in r.error

    def test_already_expired(self):
        r = svc.validate_revoke_session({"status": "expired"}, confirm=True, actions_enabled=True)
        assert not r.ok
        assert "already_expired" in r.error

    def test_success(self):
        r = svc.validate_revoke_session({"status": "active"}, confirm=True, actions_enabled=True)
        assert r.ok
        assert r.action == "session.revoke"

    def test_no_session_hash_in_result(self):
        r = svc.validate_revoke_session(
            {"status": "active", "session_id_hash": "abc"}, confirm=True, actions_enabled=True
        )
        assert "session_id_hash" not in str(r)


class TestBuildRevokeSessionDict:
    def test_revoke(self):
        d = svc.build_revoke_session_dict()
        assert d["status"] == "revoked"
        assert d["revoked_at"] != ""


class TestBuildRevokeAllFilter:
    def test_basic(self):
        f = svc.build_revoke_all_filter("u1")
        assert f["admin_id"] == "u1"
        assert f["status"] == "active"

    def test_exclude(self):
        f = svc.build_revoke_all_filter("u1", exclude_session_hash="abc")
        assert f["exclude_hash"] == "abc"


class TestValidateDisableAdmin:
    def test_disabled(self):
        r = svc.validate_disable_admin({"admin_id": "u1", "is_active": True}, actions_enabled=False)
        assert not r.ok

    def test_no_confirm(self):
        r = svc.validate_disable_admin(
            {"admin_id": "u1", "is_active": True}, confirm=False, actions_enabled=True
        )
        assert not r.ok

    def test_not_found(self):
        r = svc.validate_disable_admin(None, confirm=True, actions_enabled=True)
        assert not r.ok
        assert "not_found" in r.error

    def test_self_lockout(self):
        r = svc.validate_disable_admin(
            {"admin_id": "u1", "is_active": True, "role": "admin", "is_super_owner": False},
            actor_admin_id="u1",
            confirm=True,
            actions_enabled=True,
            active_owner_count=2,
        )
        assert not r.ok
        assert "self" in r.error

    def test_already_disabled(self):
        r = svc.validate_disable_admin(
            {"admin_id": "u2", "is_active": False, "role": "admin", "is_super_owner": False},
            actor_admin_id="u1",
            confirm=True,
            actions_enabled=True,
        )
        assert not r.ok
        assert "already_disabled" in r.error

    def test_last_owner(self):
        r = svc.validate_disable_admin(
            {"admin_id": "u2", "is_active": True, "role": "owner", "is_super_owner": False},
            actor_admin_id="u1",
            confirm=True,
            actions_enabled=True,
            active_owner_count=1,
        )
        assert not r.ok
        assert "last_owner" in r.error

    def test_super_owner(self):
        r = svc.validate_disable_admin(
            {"admin_id": "u2", "is_active": True, "role": "owner", "is_super_owner": True},
            actor_admin_id="u1",
            confirm=True,
            actions_enabled=True,
            active_owner_count=2,
        )
        assert not r.ok
        assert "super_owner" in r.error

    def test_success(self):
        r = svc.validate_disable_admin(
            {"admin_id": "u2", "is_active": True, "role": "admin", "is_super_owner": False},
            actor_admin_id="u1",
            confirm=True,
            actions_enabled=True,
            active_owner_count=2,
        )
        assert r.ok


class TestValidateEnableAdmin:
    def test_disabled(self):
        r = svc.validate_enable_admin({"is_active": False}, actions_enabled=False)
        assert not r.ok

    def test_not_found(self):
        r = svc.validate_enable_admin(None, actions_enabled=True, confirm=True)
        assert not r.ok

    def test_already_active(self):
        r = svc.validate_enable_admin({"is_active": True}, actions_enabled=True, confirm=True)
        assert not r.ok
        assert "already_active" in r.error

    def test_success(self):
        r = svc.validate_enable_admin({"is_active": False}, actions_enabled=True, confirm=True)
        assert r.ok


class TestValidateIPPattern:
    def test_valid_ip(self):
        assert svc.validate_ip_pattern("192.168.1.1").ok

    def test_valid_cidr(self):
        assert svc.validate_ip_pattern("10.0.0.0/8").ok

    def test_empty(self):
        assert not svc.validate_ip_pattern("").ok

    def test_invalid(self):
        assert not svc.validate_ip_pattern("abc.def").ok

    def test_octet_overflow(self):
        assert not svc.validate_ip_pattern("256.1.1.1").ok

    def test_whitespace_trimmed(self):
        assert svc.validate_ip_pattern("  1.2.3.4  ").ok


class TestValidateRuleType:
    def test_allow(self):
        assert svc.validate_rule_type("allow").ok

    def test_block(self):
        assert svc.validate_rule_type("block").ok

    def test_watch(self):
        assert svc.validate_rule_type("watch").ok

    def test_invalid(self):
        assert not svc.validate_rule_type("hack").ok


class TestBuildIPRuleDict:
    def test_basic(self):
        d = svc.build_ip_rule_dict("1.2.3.4", "block", "suspicious", "admin1")
        assert d["ip_pattern"] == "1.2.3.4"
        assert d["rule_type"] == "block"
        assert d["is_active"] is True
        assert d["created_by"] == "admin1"

    def test_reason_sanitized(self):
        d = svc.build_ip_rule_dict("1.2.3.4", "watch", "sk-secret error")
        assert "sk-" not in d["reason"]


class TestBuildDisableIPRuleDict:
    def test_disable(self):
        d = svc.build_disable_ip_rule_dict("admin1")
        assert d["is_active"] is False
        assert d["disabled_at"] != ""
        assert d["updated_by"] == "admin1"


class TestEvaluateIPAccess:
    def test_no_rules(self):
        r = svc.evaluate_ip_access("1.1.1.1", [])
        assert r.decision == "unknown"

    def test_exact_block(self):
        rules = [{"ip_pattern": "1.1.1.1", "rule_type": "block", "is_active": True}]
        r = svc.evaluate_ip_access("1.1.1.1", rules, enforcement_enabled=True)
        assert r.decision == "block"
        assert r.matched_rule_type == "block"

    def test_exact_allow(self):
        rules = [{"ip_pattern": "2.2.2.2", "rule_type": "allow", "is_active": True}]
        r = svc.evaluate_ip_access("2.2.2.2", rules, enforcement_enabled=True)
        assert r.decision == "allow"

    def test_watch_rule(self):
        rules = [{"ip_pattern": "3.3.3.3", "rule_type": "watch", "is_active": True}]
        r = svc.evaluate_ip_access("3.3.3.3", rules, enforcement_enabled=True)
        assert r.decision == "watch"

    def test_enforcement_off_advisory(self):
        rules = [{"ip_pattern": "1.1.1.1", "rule_type": "block", "is_active": True}]
        r = svc.evaluate_ip_access("1.1.1.1", rules, enforcement_enabled=False)
        assert r.decision == "advisory"
        assert r.matched_rule_type == "block"

    def test_inactive_rule_ignored(self):
        rules = [{"ip_pattern": "1.1.1.1", "rule_type": "block", "is_active": False}]
        r = svc.evaluate_ip_access("1.1.1.1", rules, enforcement_enabled=True)
        assert r.decision == "unknown"

    def test_no_match(self):
        rules = [{"ip_pattern": "9.9.9.9", "rule_type": "block", "is_active": True}]
        r = svc.evaluate_ip_access("1.1.1.1", rules, enforcement_enabled=True)
        assert r.decision == "unknown"


class TestGetRuleTypes:
    def test_three_types(self):
        t = svc.get_rule_types()
        assert len(t) == 3
        assert "allow" in t
        assert "block" in t
        assert "watch" in t


class TestBuildActionAudit:
    def test_success(self):
        a = svc.build_action_audit("u1", "session.revoke", "session", "123", "success", "revoked")
        assert a["actor_admin_id"] == "u1"
        assert a["action"] == "session.revoke"
        assert a["status"] == "success"

    def test_blocked(self):
        a = svc.build_action_audit("u1", "admin.disable", status="denied", reason="no perm")
        assert a["status"] == "denied"

    def test_failed(self):
        a = svc.build_action_audit("u1", "ip.create", status="failed", reason="db error")
        assert a["status"] == "failed"

    def test_reason_sanitized(self):
        a = svc.build_action_audit("u1", "test", reason="sk-secret error")
        assert "sk-" not in a["reason"]

    def test_metadata_sanitized(self):
        a = svc.build_action_audit("u1", "test", metadata={"t": "sk-secret"})
        assert "[REDACTED]" in a["metadata_json"]["t"]


class TestSanitizeReason:
    def test_empty(self):
        assert svc.sanitize_reason("") == ""

    def test_clean(self):
        assert svc.sanitize_reason("ok") == "ok"

    def test_token(self):
        assert "sk-" not in svc.sanitize_reason("sk-secret error")

    def test_truncated(self):
        assert len(svc.sanitize_reason("x" * 1000)) <= 500


class TestSanitizeResult:
    def test_removes_hash(self):
        d = svc.sanitize_result({"session_id_hash": "abc", "ok": True})
        assert "session_id_hash" not in d

    def test_removes_session_id(self):
        d = svc.sanitize_result({"session_id": "abc", "ok": True})
        assert "session_id" not in d

    def test_redacts_tokens(self):
        d = svc.sanitize_result({"note": "sk-secret123"})
        assert "[REDACTED]" in d["note"]


class TestImmutability:
    def test_result_frozen(self):
        import pytest

        from core.services.admin_security_action_service import SecurityActionResult

        r = SecurityActionResult(ok=True)
        with pytest.raises(AttributeError):
            r.ok = False  # type: ignore[misc]

    def test_ip_eval_frozen(self):
        import pytest

        from core.services.admin_security_action_service import IPEvaluationResult

        r = IPEvaluationResult()
        with pytest.raises(AttributeError):
            r.decision = "x"  # type: ignore[misc]
