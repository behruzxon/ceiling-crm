"""Tests for Step BM — Security Enablement Docs."""
from __future__ import annotations

from pathlib import Path


class TestDocsExist:
    def test_enablement_plan(self):
        assert Path("docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md").exists()

    def test_preflight_runbook(self):
        assert Path("docs/AI_AGENT_SYSTEM/70_SECURITY_PREFLIGHT_RUNBOOK.md").exists()

    def test_rollback_card(self):
        assert Path("docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md").exists()

    def test_staging_test_script(self):
        assert Path("docs/AI_AGENT_SYSTEM/72_SECURITY_STAGING_TEST_SCRIPT.md").exists()


class TestEnablementPlan:
    def test_contains_stages(self):
        content = Path("docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md").read_text(encoding="utf-8")
        for stage in ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]:
            assert stage in content

    def test_contains_do_not_enable(self):
        content = Path("docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md").read_text(encoding="utf-8")
        assert "Do Not Enable" in content or "do not" in content.lower()

    def test_contains_rollback(self):
        content = Path("docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md").read_text(encoding="utf-8")
        assert "rollback" in content.lower()

    def test_contains_preflight(self):
        content = Path("docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md").read_text(encoding="utf-8")
        assert "preflight" in content.lower()


class TestRollbackCard:
    def test_disable_session_auth(self):
        content = Path("docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md").read_text(encoding="utf-8")
        assert "SESSION_AUTH" in content

    def test_disable_csrf(self):
        content = Path("docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md").read_text(encoding="utf-8")
        assert "CSRF" in content

    def test_disable_db_rbac(self):
        content = Path("docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md").read_text(encoding="utf-8")
        assert "DB_RBAC" in content

    def test_restart_step(self):
        content = Path("docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md").read_text(encoding="utf-8")
        assert "restart" in content.lower() or "Restart" in content

    def test_owner_lockout_recovery(self):
        content = Path("docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md").read_text(encoding="utf-8")
        assert "lockout" in content.lower()


class TestRunbook:
    def test_how_to_run(self):
        content = Path("docs/AI_AGENT_SYSTEM/70_SECURITY_PREFLIGHT_RUNBOOK.md").read_text(encoding="utf-8")
        assert "security_enablement_preflight" in content

    def test_status_meanings(self):
        content = Path("docs/AI_AGENT_SYSTEM/70_SECURITY_PREFLIGHT_RUNBOOK.md").read_text(encoding="utf-8")
        assert "GREEN" in content
        assert "YELLOW" in content
        assert "RED" in content

    def test_no_secrets_note(self):
        content = Path("docs/AI_AGENT_SYSTEM/70_SECURITY_PREFLIGHT_RUNBOOK.md").read_text(encoding="utf-8")
        assert "secret" in content.lower()


class TestStagingTestScript:
    def test_manual_scenarios(self):
        content = Path("docs/AI_AGENT_SYSTEM/72_SECURITY_STAGING_TEST_SCRIPT.md").read_text(encoding="utf-8")
        assert "owner login" in content.lower() or "Owner login" in content

    def test_rollback_test(self):
        content = Path("docs/AI_AGENT_SYSTEM/72_SECURITY_STAGING_TEST_SCRIPT.md").read_text(encoding="utf-8")
        assert "rollback" in content.lower()

    def test_no_real_secrets(self):
        content = Path("docs/AI_AGENT_SYSTEM/72_SECURITY_STAGING_TEST_SCRIPT.md").read_text(encoding="utf-8")
        assert "sk-" not in content
        assert "Bearer " not in content


class TestScript:
    def test_script_exists(self):
        assert Path("scripts/security_enablement_preflight.py").exists()

    def test_script_importable(self):
        import importlib
        mod = importlib.import_module("scripts.security_enablement_preflight")
        assert callable(mod.main)
        assert callable(mod.gather_settings)
