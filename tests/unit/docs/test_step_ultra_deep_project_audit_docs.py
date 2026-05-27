"""Tests for Ultra Deep Project Audit Docs."""
from __future__ import annotations

from pathlib import Path

_D = "docs/AI_AGENT_SYSTEM"


def _r(n: str) -> str:
    return Path(f"{_D}/{n}").read_text(encoding="utf-8")


class TestDocsExist:
    def test_109(self):
        assert Path(f"{_D}/109_ULTRA_DEEP_PROJECT_AUDIT.md").exists()

    def test_110(self):
        assert Path(f"{_D}/110_PROJECT_RISK_REGISTER.md").exists()

    def test_111(self):
        assert Path(f"{_D}/111_NEXT_30_STEP_MASTER_ROADMAP.md").exists()

    def test_112(self):
        assert Path(f"{_D}/112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md").exists()


class TestAuditDoc:
    def test_architecture(self):
        assert "Architecture" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")

    def test_bot_audit(self):
        assert "Bot" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")

    def test_ai_audit(self):
        assert "AI" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")

    def test_web_audit(self):
        assert "Web" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md") or "CRM" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")

    def test_db_audit(self):
        c = _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")
        assert "Database" in c or "Migration" in c

    def test_security_audit(self):
        assert "Security" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")

    def test_deploy_audit(self):
        assert "Deploy" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")

    def test_scores(self):
        assert "/10" in _r("109_ULTRA_DEEP_PROJECT_AUDIT.md")


class TestRiskRegister:
    def test_has_table(self):
        c = _r("110_PROJECT_RISK_REGISTER.md")
        assert "Risk" in c and "|" in c

    def test_severity(self):
        c = _r("110_PROJECT_RISK_REGISTER.md")
        assert "HIGH" in c or "MEDIUM" in c

    def test_mitigation(self):
        assert "Mitigation" in _r("110_PROJECT_RISK_REGISTER.md")

    def test_fix_stage(self):
        c = _r("110_PROJECT_RISK_REGISTER.md")
        assert "P0" in c or "P1" in c


class TestRoadmap:
    def test_30_steps(self):
        c = _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")
        assert "30" in c or "| 30 |" in c

    def test_p0(self):
        assert "P0" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")

    def test_p1(self):
        assert "P1" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")

    def test_p2(self):
        assert "P2" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")

    def test_p3(self):
        assert "P3" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")

    def test_p4(self):
        assert "P4" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")

    def test_p5(self):
        assert "P5" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")

    def test_migration_column(self):
        assert "Migration" in _r("111_NEXT_30_STEP_MASTER_ROADMAP.md")


class TestGoNoGo:
    def test_verdict(self):
        c = _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")
        assert "CONDITIONAL GO" in c

    def test_db_backup(self):
        c = _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")
        assert "backup" in c.lower()

    def test_alembic(self):
        assert "alembic upgrade head" in _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")

    def test_log_only(self):
        assert "LOG_ONLY" in _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")

    def test_rollback(self):
        c = _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")
        assert "Rollback" in c or "rollback" in c

    def test_blockers(self):
        assert "Blocker" in _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")

    def test_apply_steps(self):
        assert "Apply" in _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")


class TestNoSecrets:
    def test_not_deployed(self):
        for n in ["109", "110", "111", "112"]:
            fn = [
                f for f in Path(_D).iterdir()
                if f.name.startswith(n)
            ]
            if fn:
                c = fn[0].read_text(encoding="utf-8")
                assert "deployed to production" not in c.lower()

    def test_not_applied(self):
        c = _r("112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md")
        assert "NOT APPLIED" in c

    def test_no_token(self):
        for name in [
            "109_ULTRA_DEEP_PROJECT_AUDIT.md",
            "110_PROJECT_RISK_REGISTER.md",
            "111_NEXT_30_STEP_MASTER_ROADMAP.md",
            "112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md",
        ]:
            c = _r(name)
            assert "sk-proj-" not in c
            assert "sk-ant-" not in c

    def test_no_openai_key(self):
        for name in [
            "109_ULTRA_DEEP_PROJECT_AUDIT.md",
            "112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md",
        ]:
            assert "OPENAI_API_KEY=" not in _r(name)

    def test_no_db_url(self):
        for name in [
            "109_ULTRA_DEEP_PROJECT_AUDIT.md",
            "112_STAGE_1_GO_NO_GO_EXECUTIVE_SUMMARY.md",
        ]:
            assert "postgresql://" not in _r(name)


class TestSmoke:
    def test_bot(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_price(self):
        from core.services.price_calculator_service import PriceCalculatorService
        assert PriceCalculatorService is not None

    def test_handoff(self):
        from core.services.crm_operator_handoff_service import build_user_message
        assert callable(build_user_message)

    def test_simulator(self):
        from core.services.agent_quality_simulator_service import AgentQualitySimulatorService
        assert AgentQualitySimulatorService is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None

    def test_api(self):
        from apps.api.main import app
        assert app is not None
