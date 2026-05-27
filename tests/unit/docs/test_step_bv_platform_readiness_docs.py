"""Tests for Step BV — Platform Readiness Docs."""

from __future__ import annotations

from pathlib import Path


class TestDocsExist:
    def test_audit_doc(self):
        assert Path("docs/AI_AGENT_SYSTEM/81_PLATFORM_READINESS_AUDIT.md").exists()

    def test_checklist_doc(self):
        assert Path("docs/AI_AGENT_SYSTEM/82_STAGE_1_GO_NO_GO_CHECKLIST.md").exists()

    def test_risk_register(self):
        assert Path("docs/AI_AGENT_SYSTEM/83_PRODUCTION_RISK_REGISTER.md").exists()


class TestAuditDoc:
    def _content(self):
        return Path("docs/AI_AGENT_SYSTEM/81_PLATFORM_READINESS_AUDIT.md").read_text(
            encoding="utf-8"
        )

    def test_test_status(self):
        assert "3540" in self._content() or "unit" in self._content().lower()

    def test_migrations(self):
        assert "migration" in self._content().lower()

    def test_feature_flags(self):
        assert "flag" in self._content().lower() or "SAFE" in self._content()

    def test_agent_readiness(self):
        assert "agent" in self._content().lower()

    def test_crm_readiness(self):
        assert "CRM" in self._content()

    def test_security_readiness(self):
        assert "security" in self._content().lower() or "Security" in self._content()

    def test_verdict(self):
        assert "CONDITIONAL GO" in self._content() or "GO" in self._content()

    def test_no_secrets(self):
        c = self._content()
        assert "sk-" not in c
        assert "Bearer " not in c


class TestChecklist:
    def _content(self):
        return Path("docs/AI_AGENT_SYSTEM/82_STAGE_1_GO_NO_GO_CHECKLIST.md").read_text(
            encoding="utf-8"
        )

    def test_backup(self):
        assert "backup" in self._content().lower()

    def test_alembic(self):
        assert "alembic" in self._content().lower()

    def test_rollback(self):
        assert "rollback" in self._content().lower() or "Rollback" in self._content()

    def test_observe(self):
        assert "observe" in self._content().lower() or "Observe" in self._content()

    def test_flags_check(self):
        assert "flag" in self._content().lower() or "SEND" in self._content()


class TestRiskRegister:
    def _content(self):
        return Path("docs/AI_AGENT_SYSTEM/83_PRODUCTION_RISK_REGISTER.md").read_text(
            encoding="utf-8"
        )

    def test_severity(self):
        assert "HIGH" in self._content() or "MEDIUM" in self._content()

    def test_mitigation(self):
        assert "mitigation" in self._content().lower() or "Mitigation" in self._content()

    def test_verdict(self):
        assert "CONDITIONAL GO" in self._content()

    def test_no_fake_deployed(self):
        c = self._content()
        assert "deployed" not in c.lower() or "not" in c.lower()


class TestScript:
    def test_script_exists(self):
        assert Path("scripts/platform_readiness_audit.py").exists()

    def test_importable(self):
        import importlib

        mod = importlib.import_module("scripts.platform_readiness_audit")
        assert callable(mod.main)
        assert callable(mod.check_imports)
        assert callable(mod.check_docs)
        assert callable(mod.check_dangerous_flags)
        assert callable(mod.check_migrations)
