"""Tests for Step BM — Security Enablement Preflight."""

from __future__ import annotations

from core.services.security_enablement_service import SecurityEnablementService

svc = SecurityEnablementService


def _defaults():
    return {
        "app_env": "development",
        "admin_rbac_enabled": False,
        "admin_db_rbac_enabled": False,
        "admin_db_rbac_fallback_to_env": True,
        "admin_session_auth_enabled": False,
        "admin_session_secure_cookie": True,
        "admin_csrf_enabled": False,
        "admin_security_actions_enabled": False,
        "admin_security_action_audit_enabled": True,
        "admin_ip_rules_enabled": False,
        "admin_ip_block_enforcement_enabled": False,
        "admin_login_max_attempts": 5,
    }


class TestDefaultSafeMode:
    def test_all_off_green(self):
        r = svc.run_preflight(_defaults())
        assert r.overall == "green"
        assert r.can_proceed
        assert len(r.blockers) == 0

    def test_stage_s0(self):
        r = svc.run_preflight(_defaults())
        assert r.stage == "S0"

    def test_safe_mode_check(self):
        r = svc.run_preflight(_defaults())
        assert any(c.name == "safe_mode" for c in r.checks)


class TestSessionAuthChecks:
    def test_session_no_secret_red(self):
        s = _defaults()
        s["admin_session_auth_enabled"] = True
        r = svc.run_preflight(s, has_secret_key=False)
        assert r.overall == "red"
        assert not r.can_proceed
        assert any("secret" in b.lower() for b in r.blockers)

    def test_session_with_secret_ok(self):
        s = _defaults()
        s["admin_session_auth_enabled"] = True
        r = svc.run_preflight(s, has_secret_key=True)
        assert any(c.name == "secret_key" and c.status == "green" for c in r.checks)


class TestDBRBACChecks:
    def test_db_rbac_no_owner_no_fallback_red(self):
        s = _defaults()
        s["admin_db_rbac_enabled"] = True
        s["admin_db_rbac_fallback_to_env"] = False
        r = svc.run_preflight(s, has_db_owner=False)
        assert r.overall == "red"
        assert not r.can_proceed
        assert any("lockout" in b.lower() for b in r.blockers)

    def test_db_rbac_no_owner_fallback_yellow(self):
        s = _defaults()
        s["admin_db_rbac_enabled"] = True
        s["admin_db_rbac_fallback_to_env"] = True
        r = svc.run_preflight(s, has_db_owner=False)
        assert any(c.name == "db_rbac_owner" and c.status == "yellow" for c in r.checks)
        assert len(r.warnings) > 0

    def test_db_rbac_with_owner_green(self):
        s = _defaults()
        s["admin_db_rbac_enabled"] = True
        r = svc.run_preflight(s, has_db_owner=True)
        assert any(c.name == "db_rbac_owner" and c.status == "green" for c in r.checks)


class TestCSRFChecks:
    def test_csrf_no_session_red(self):
        s = _defaults()
        s["admin_csrf_enabled"] = True
        s["admin_session_auth_enabled"] = False
        r = svc.run_preflight(s)
        assert any(c.name == "csrf_session" and c.status == "red" for c in r.checks)
        assert not r.can_proceed

    def test_csrf_with_session_green(self):
        s = _defaults()
        s["admin_csrf_enabled"] = True
        s["admin_session_auth_enabled"] = True
        r = svc.run_preflight(s, has_secret_key=True)
        assert any(c.name == "csrf_session" and c.status == "green" for c in r.checks)


class TestSecurityActionsChecks:
    def test_actions_no_audit_yellow(self):
        s = _defaults()
        s["admin_security_actions_enabled"] = True
        s["admin_security_action_audit_enabled"] = False
        r = svc.run_preflight(s)
        assert any(c.name == "actions_audit" and c.status == "yellow" for c in r.checks)

    def test_actions_with_audit_green(self):
        s = _defaults()
        s["admin_security_actions_enabled"] = True
        s["admin_security_action_audit_enabled"] = True
        r = svc.run_preflight(s)
        assert any(c.name == "actions_audit" and c.status == "green" for c in r.checks)


class TestIPEnforcementChecks:
    def test_enforcement_no_fallback_red(self):
        s = _defaults()
        s["admin_ip_block_enforcement_enabled"] = True
        s["admin_db_rbac_fallback_to_env"] = False
        r = svc.run_preflight(s)
        assert not r.can_proceed

    def test_enforcement_with_fallback_green(self):
        s = _defaults()
        s["admin_ip_block_enforcement_enabled"] = True
        s["admin_db_rbac_fallback_to_env"] = True
        r = svc.run_preflight(s)
        assert any(c.name == "ip_enforcement_fallback" and c.status == "green" for c in r.checks)


class TestSecureCookieDev:
    def test_secure_cookie_dev_yellow(self):
        s = _defaults()
        s["admin_session_auth_enabled"] = True
        s["admin_session_secure_cookie"] = True
        s["app_env"] = "development"
        r = svc.run_preflight(s, has_secret_key=True)
        assert any(c.name == "secure_cookie_dev" and c.status == "yellow" for c in r.checks)


class TestLoginMaxAttempts:
    def test_low_attempts_yellow(self):
        s = _defaults()
        s["admin_login_max_attempts"] = 2
        r = svc.run_preflight(s)
        assert any("max_attempts" in c.name and c.status == "yellow" for c in r.checks)


class TestStageDetection:
    def test_detect_s0(self):
        assert svc.detect_current_stage(_defaults()) == "S0"

    def test_detect_s1(self):
        s = _defaults()
        s["admin_rbac_enabled"] = True
        assert svc.detect_current_stage(s) == "S1"

    def test_get_stage_flags(self):
        f = svc.get_stage_flags("S3")
        assert f["admin_session_auth_enabled"] is True
        assert f["admin_csrf_enabled"] is False


class TestRollbackCard:
    def test_rollback_from_s3(self):
        card = svc.build_rollback_card("S3")
        assert card.from_stage == "S3"
        assert card.to_stage == "S2"
        assert len(card.steps) > 0

    def test_rollback_from_s0(self):
        card = svc.build_rollback_card("S0")
        assert card.to_stage == "S0"

    def test_rollback_includes_restart(self):
        card = svc.build_rollback_card("S5")
        assert any("restart" in s.lower() for s in card.steps)

    def test_rollback_includes_verify(self):
        card = svc.build_rollback_card("S5")
        assert any("verify" in s.lower() for s in card.steps)


class TestConfigMatrix:
    def test_eight_stages(self):
        m = svc.build_config_matrix()
        assert len(m) == 8

    def test_each_has_flags(self):
        m = svc.build_config_matrix()
        for entry in m:
            assert "flags" in entry
            assert "stage" in entry
            assert "description" in entry


class TestNavigation:
    def test_next_stage(self):
        assert svc.get_next_stage("S0") == "S1"
        assert svc.get_next_stage("S6") == "S7"
        assert svc.get_next_stage("S7") is None

    def test_previous_stage(self):
        assert svc.get_previous_stage("S7") == "S6"
        assert svc.get_previous_stage("S0") is None

    def test_get_stages(self):
        stages = svc.get_stages()
        assert len(stages) == 8
        assert stages[0] == "S0"
        assert stages[-1] == "S7"


class TestNoSecretsPrinted:
    def test_preflight_no_secret_in_report(self):
        r = svc.run_preflight(_defaults(), has_secret_key=True)
        report_str = str(r)
        assert "sk-" not in report_str
        assert "token" not in report_str.lower() or "token" in "confirmation_required"


class TestImmutability:
    def test_preflight_check_frozen(self):
        import pytest

        from core.services.security_enablement_service import PreflightCheck

        c = PreflightCheck()
        with pytest.raises(AttributeError):
            c.status = "x"  # type: ignore[misc]

    def test_preflight_report_frozen(self):
        import pytest

        from core.services.security_enablement_service import PreflightReport

        r = PreflightReport()
        with pytest.raises(AttributeError):
            r.stage = "x"  # type: ignore[misc]

    def test_rollback_card_frozen(self):
        import pytest

        from core.services.security_enablement_service import RollbackCard

        c = RollbackCard()
        with pytest.raises(AttributeError):
            c.from_stage = "x"  # type: ignore[misc]
