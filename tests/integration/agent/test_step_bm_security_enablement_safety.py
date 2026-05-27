"""Integration tests for Step BM — Security Enablement Safety."""
from __future__ import annotations


class TestDefaultConfigOldAuthWorks:
    def test_dashboard_auth_importable(self):
        from apps.web.auth import require_dashboard_auth
        assert callable(require_dashboard_auth)

    def test_api_app_ok(self):
        from apps.api.main import app
        assert app is not None

    def test_web_app_ok(self):
        from apps.web.main import app
        assert app is not None


class TestDBRBACFallbackPreventsLockout:
    def test_no_db_user_fallback_resolves(self):
        from core.services.admin_rbac_service import AdminRBACService
        role, src = AdminRBACService.resolve_role_with_db(
            "u1", None, db_rbac_enabled=True, fallback_to_env=True,
            owner_ids="u1",
        )
        assert role == "owner"
        assert src == "env"

    def test_no_owner_no_fallback_preflight_red(self):
        from core.services.security_enablement_service import SecurityEnablementService
        s = {
            "admin_db_rbac_enabled": True,
            "admin_db_rbac_fallback_to_env": False,
        }
        r = SecurityEnablementService.run_preflight(s, has_db_owner=False)
        assert not r.can_proceed


class TestIPEnforcementDisabledNoBlock:
    def test_enforcement_off_advisory(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        rule = {"ip_pattern": "1.1.1.1", "rule_type": "block", "is_active": True}
        r = AdminSecurityActionService.evaluate_ip_access("1.1.1.1", [rule], enforcement_enabled=False)
        assert r.decision == "advisory"


class TestActionsDisabledBlocksMutations:
    def test_revoke_blocked(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        r = AdminSecurityActionService.validate_revoke_session(
            {"status": "active"}, confirm=True, actions_enabled=False,
        )
        assert not r.ok
        assert "disabled" in r.error

    def test_disable_blocked(self):
        from core.services.admin_security_action_service import AdminSecurityActionService
        r = AdminSecurityActionService.validate_disable_admin(
            {"admin_id": "u1", "is_active": True, "role": "admin", "is_super_owner": False},
            actor_admin_id="u2", confirm=True, actions_enabled=False,
        )
        assert not r.ok


class TestNoSendOccurs:
    def test_no_telegram_in_enablement_service(self):
        import inspect

        import core.services.security_enablement_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src


class TestNoTokenLeak:
    def test_preflight_no_secrets(self):
        from core.services.security_enablement_service import SecurityEnablementService
        r = SecurityEnablementService.run_preflight({}, has_secret_key=True)
        report_str = str(r)
        assert "sk-" not in report_str


class TestStageProgression:
    def test_s0_to_s7(self):
        from core.services.security_enablement_service import SecurityEnablementService
        stages = SecurityEnablementService.get_stages()
        for i, stage in enumerate(stages):
            desc = SecurityEnablementService.get_stage_description(stage)
            assert len(desc) > 5
            flags = SecurityEnablementService.get_stage_flags(stage)
            assert isinstance(flags, dict)

    def test_each_stage_has_rollback(self):
        from core.services.security_enablement_service import SecurityEnablementService
        for stage in SecurityEnablementService.get_stages()[1:]:
            card = SecurityEnablementService.build_rollback_card(stage)
            assert card.from_stage == stage
            assert len(card.steps) > 0


class TestSmoke:
    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
