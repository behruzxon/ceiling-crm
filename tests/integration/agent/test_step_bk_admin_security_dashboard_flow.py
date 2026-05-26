"""Integration tests for Step BK — Admin Security Dashboard flow."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone


class TestLoginAppearsInDashboard:
    def test_failed_login_in_metrics(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        from core.services.admin_auth_service import AdminAuthService
        attempt = AdminAuthService.record_login_attempt("u1", "1.1.1.1", "failed", "bad creds")
        m = AdminSecurityAuditService.get_login_attempt_metrics([attempt])
        assert m.failed == 1

    def test_success_login_in_metrics(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        from core.services.admin_auth_service import AdminAuthService
        attempt = AdminAuthService.record_login_attempt("u1", "1.1.1.1", "success")
        m = AdminSecurityAuditService.get_login_attempt_metrics([attempt])
        assert m.successful == 1


class TestSessionAppearsActive:
    def test_session_active(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        from core.services.admin_auth_service import AdminAuthService
        cr = AdminAuthService.create_session("admin1", "admin")
        d = AdminAuthService.build_session_dict(cr, ip_address="1.1.1.1")
        m = AdminSecurityAuditService.get_session_metrics([d])
        assert m.active == 1


class TestPermissionDeniedInDashboard:
    def test_denied_audit(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        from core.services.admin_audit_log_service import AdminAuditLogService
        entry = AdminAuditLogService.build_denial_entry(
            actor_admin_id="op1", actor_role="operator",
            action="settings.mutate", reason="no permission",
        )
        m = AdminSecurityAuditService.get_permission_denied_metrics([entry])
        assert m.total_denied == 1
        assert m.by_actor[0][0] == "op1"


class TestSensitiveActionInDashboard:
    def test_sensitive_action(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        from core.services.admin_audit_log_service import AdminAuditLogService
        entry = AdminAuditLogService.build_entry(
            actor_admin_id="adm1", action="crm.reply.send", status="success",
        )
        m = AdminSecurityAuditService.get_sensitive_action_metrics([entry])
        assert m.total == 1


class TestSuspiciousDetection:
    def test_failed_ip_detected(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        from core.services.admin_auth_service import AdminAuthService
        attempts = [AdminAuthService.record_login_attempt("u1", "5.5.5.5", "failed") for _ in range(6)]
        lm = AdminSecurityAuditService.get_login_attempt_metrics(attempts)
        from core.services.admin_security_audit_service import SessionMetrics, PermissionDeniedMetrics, SensitiveActionMetrics
        indicators = AdminSecurityAuditService.detect_suspicious_activity(
            lm, SessionMetrics(), PermissionDeniedMetrics(), SensitiveActionMetrics(),
        )
        assert any(i.rule == "brute_force_ip" for i in indicators)


class TestRBACPermission:
    def test_system_audit_can_view(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("owner", "system.audit")
        assert AdminRBACService.has_permission("admin", "system.audit")

    def test_viewer_cannot_view_audit(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("viewer", "system.audit")

    def test_operator_cannot_view_audit(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("operator", "system.audit")


class TestNoSendOccurs:
    def test_no_telegram_in_service(self):
        import inspect
        import core.services.admin_security_audit_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src


class TestNoTokenLeak:
    def test_metadata_sanitized(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        d = AdminSecurityAuditService.sanitize_audit_metadata({"t": "sk-secret"})
        assert "[REDACTED]" in d["t"]

    def test_user_agent_sanitized(self):
        from core.services.admin_security_audit_service import AdminSecurityAuditService
        ua = AdminSecurityAuditService.sanitize_user_agent("sk-secret browser")
        assert "sk-" not in ua


class TestSmoke:
    def test_api_importable(self):
        from apps.api.main import app
        assert app is not None

    def test_web_importable(self):
        from apps.web.main import app
        assert app is not None

    def test_scheduler_importable(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
