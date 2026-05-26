"""Integration tests for Step BL — Security Actions flow."""
from __future__ import annotations


class TestSessionRevokeFlow:
    def test_revoke_active_session(self):
        from core.services.admin_auth_service import AdminAuthService
        from core.services.admin_security_action_service import AdminSecurityActionService
        cr = AdminAuthService.create_session("admin1", "admin")
        d = AdminAuthService.build_session_dict(cr)
        v = AdminSecurityActionService.validate_revoke_session(d, confirm=True, actions_enabled=True)
        assert v.ok
        revoke = AdminSecurityActionService.build_revoke_session_dict()
        d.update(revoke)
        vr = AdminAuthService.validate_session(d)
        assert not vr.ok
        assert "revoked" in vr.error

    def test_revoke_already_revoked(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        d = {"status": "revoked"}
        v = AdminSecurityActionService.validate_revoke_session(d, confirm=True, actions_enabled=True)
        assert not v.ok


class TestDisableAdminFlow:
    def test_disable_admin(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        target = {"admin_id": "u2", "is_active": True, "role": "operator", "is_super_owner": False}
        v = AdminSecurityActionService.validate_disable_admin(
            target, actor_admin_id="u1", confirm=True, actions_enabled=True, active_owner_count=2,
        )
        assert v.ok

    def test_last_owner_blocked(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        target = {"admin_id": "u2", "is_active": True, "role": "owner", "is_super_owner": False}
        v = AdminSecurityActionService.validate_disable_admin(
            target, actor_admin_id="u1", confirm=True, actions_enabled=True, active_owner_count=1,
        )
        assert not v.ok

    def test_self_lockout_blocked(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        target = {"admin_id": "u1", "is_active": True, "role": "admin", "is_super_owner": False}
        v = AdminSecurityActionService.validate_disable_admin(
            target, actor_admin_id="u1", confirm=True, actions_enabled=True,
        )
        assert not v.ok


class TestIPRuleFlow:
    def test_create_and_evaluate_block(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        rule = AdminSecurityActionService.build_ip_rule_dict("5.5.5.5", "block", "suspicious", "admin1")
        r = AdminSecurityActionService.evaluate_ip_access("5.5.5.5", [rule], enforcement_enabled=True)
        assert r.decision == "block"

    def test_enforcement_off_advisory(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        rule = AdminSecurityActionService.build_ip_rule_dict("5.5.5.5", "block")
        r = AdminSecurityActionService.evaluate_ip_access("5.5.5.5", [rule], enforcement_enabled=False)
        assert r.decision == "advisory"

    def test_watch_rule(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        rule = AdminSecurityActionService.build_ip_rule_dict("3.3.3.3", "watch")
        r = AdminSecurityActionService.evaluate_ip_access("3.3.3.3", [rule], enforcement_enabled=True)
        assert r.decision == "watch"


class TestAuditRecording:
    def test_success_audit(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        a = AdminSecurityActionService.build_action_audit(
            "admin1", "session.revoke", "session", "123", "success", "user request",
        )
        assert a["action"] == "session.revoke"
        assert a["status"] == "success"

    def test_denied_audit(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        a = AdminSecurityActionService.build_action_audit(
            "op1", "admin.disable", status="denied", reason="no permission",
        )
        assert a["status"] == "denied"


class TestNoTokenLeak:
    def test_result_sanitized(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        d = AdminSecurityActionService.sanitize_result({
            "session_id_hash": "abc", "session_id": "raw", "ok": True,
        })
        assert "session_id_hash" not in d
        assert "session_id" not in d

    def test_reason_sanitized(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        r = AdminSecurityActionService.sanitize_reason("sk-secret error")
        assert "sk-" not in r


class TestNoSendOccurs:
    def test_no_telegram_in_service(self):
        import inspect
        import core.services.admin_security_action_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src


class TestRBACIntegration:
    def test_owner_can_manage_security(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("owner", "security.manage")
        assert AdminRBACService.has_permission("owner", "security.sessions.revoke")
        assert AdminRBACService.has_permission("owner", "security.admin.disable")
        assert AdminRBACService.has_permission("owner", "security.ip_rules.manage")

    def test_admin_limited_security(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("admin", "security.sessions.revoke")
        assert not AdminRBACService.has_permission("admin", "security.manage")


class TestSmoke:
    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None

    def test_api(self):
        from apps.api.main import app
        assert app is not None
