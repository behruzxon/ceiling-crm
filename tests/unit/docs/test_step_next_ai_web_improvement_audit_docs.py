"""Tests for Deep Improvement Audit Docs."""

from __future__ import annotations

from pathlib import Path

_D = "docs/AI_AGENT_SYSTEM"


def _r(name: str) -> str:
    return Path(f"{_D}/{name}").read_text(encoding="utf-8")


class TestDocsExist:
    def test_doc_102(self):
        assert Path(f"{_D}/102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md").exists()

    def test_doc_103(self):
        assert Path(f"{_D}/103_NEXT_IMPROVEMENT_ROADMAP.md").exists()

    def test_doc_104(self):
        assert Path(f"{_D}/104_PRE_STAGE_1_FINAL_CHECKLIST.md").exists()


class TestAuditDoc:
    def test_executive_summary(self):
        assert "Executive Summary" in _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")

    def test_ai_score(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "/10" in c and "AI" in c

    def test_web_score(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "Web" in c and "/10" in c

    def test_crm_score(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "CRM" in c

    def test_production_readiness(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "Production" in c or "readiness" in c.lower()

    def test_top_risks(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "Risk" in c or "risk" in c

    def test_strengths(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "Strength" in c or "strength" in c.lower()

    def test_weaknesses(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "Weakness" in c or "weakness" in c.lower()

    def test_gaps(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "Gap" in c or "gap" in c


class TestRoadmapDoc:
    def test_immediate_steps(self):
        c = _r("103_NEXT_IMPROVEMENT_ROADMAP.md")
        assert "Immediate" in c or "immediate" in c

    def test_pre_stage_1(self):
        c = _r("103_NEXT_IMPROVEMENT_ROADMAP.md")
        assert "Pre-Stage 1" in c or "pre-stage" in c.lower()

    def test_stage_1_observation(self):
        c = _r("103_NEXT_IMPROVEMENT_ROADMAP.md")
        assert "Stage 1" in c and "Observation" in c

    def test_post_stage_1(self):
        c = _r("103_NEXT_IMPROVEMENT_ROADMAP.md")
        assert "Post-Stage 1" in c or "post-stage" in c.lower()

    def test_future_premium(self):
        c = _r("103_NEXT_IMPROVEMENT_ROADMAP.md")
        assert "Future" in c or "Premium" in c

    def test_next_10_steps(self):
        c = _r("103_NEXT_IMPROVEMENT_ROADMAP.md")
        assert "Next 10" in c or "next" in c.lower()


class TestChecklistDoc:
    def test_ci_checklist(self):
        c = _r("104_PRE_STAGE_1_FINAL_CHECKLIST.md")
        assert "CI" in c or "PR" in c

    def test_vps_checklist(self):
        assert "VPS" in _r("104_PRE_STAGE_1_FINAL_CHECKLIST.md")

    def test_backup_checklist(self):
        c = _r("104_PRE_STAGE_1_FINAL_CHECKLIST.md")
        assert "Backup" in c or "backup" in c

    def test_migration_checklist(self):
        c = _r("104_PRE_STAGE_1_FINAL_CHECKLIST.md")
        assert "Migration" in c or "migration" in c or "alembic" in c

    def test_log_only_checklist(self):
        assert "LOG_ONLY" in _r("104_PRE_STAGE_1_FINAL_CHECKLIST.md")

    def test_rollback_checklist(self):
        c = _r("104_PRE_STAGE_1_FINAL_CHECKLIST.md")
        assert "Rollback" in c or "rollback" in c


class TestNoSecrets:
    def test_no_deployed_claim_102(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "NOT DEPLOYED" in c

    def test_no_stage1_applied_102(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "NOT APPLIED" in c

    def test_no_token_102(self):
        c = _r("102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md")
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_openai_key(self):
        for name in [
            "102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md",
            "103_NEXT_IMPROVEMENT_ROADMAP.md",
            "104_PRE_STAGE_1_FINAL_CHECKLIST.md",
        ]:
            c = _r(name)
            assert "OPENAI_API_KEY=" not in c

    def test_no_db_url(self):
        for name in [
            "102_AI_AGENT_WEB_IMPROVEMENT_AUDIT.md",
            "103_NEXT_IMPROVEMENT_ROADMAP.md",
            "104_PRE_STAGE_1_FINAL_CHECKLIST.md",
        ]:
            c = _r(name)
            assert "postgresql://" not in c
