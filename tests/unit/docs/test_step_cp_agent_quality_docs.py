"""Tests for Step CP — Agent Quality Docs."""

from __future__ import annotations

from pathlib import Path

_D = "docs/AI_AGENT_SYSTEM"


def _r(name: str) -> str:
    return Path(f"{_D}/{name}").read_text(encoding="utf-8")


class TestDocsExist:
    def test_doc_105(self):
        assert Path(f"{_D}/105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md").exists()

    def test_doc_106(self):
        assert Path(f"{_D}/106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md").exists()


class TestSimulatorDoc:
    def test_scoring_method(self):
        assert "Scoring" in _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")

    def test_scenario_categories(self):
        c = _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")
        assert "Price" in c and "Objection" in c

    def test_safety_findings(self):
        c = _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")
        assert "Safety" in c or "safety" in c

    def test_strengths(self):
        c = _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")
        assert "Strength" in c or "strong" in c.lower()

    def test_weak_cases(self):
        c = _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")
        assert "Weak" in c or "weak" in c.lower()


class TestImprovementDoc:
    def test_improvement_plan(self):
        c = _r("106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md")
        assert "Improvement" in c or "improvement" in c

    def test_prompt_fixes(self):
        c = _r("106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md")
        assert "Prompt" in c or "prompt" in c

    def test_stage_1_metrics(self):
        c = _r("106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md")
        assert "Stage 1" in c

    def test_post_stage_1(self):
        c = _r("106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md")
        assert "Post" in c or "post" in c.lower()


class TestNoSecrets:
    def test_not_deployed_105(self):
        assert "NOT DEPLOYED" in _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")

    def test_not_deployed_106(self):
        assert "NOT DEPLOYED" in _r("106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md")

    def test_no_token_105(self):
        c = _r("105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md")
        assert "sk-proj-" not in c

    def test_no_token_106(self):
        c = _r("106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md")
        assert "sk-proj-" not in c

    def test_no_db_url(self):
        for name in [
            "105_AI_AGENT_QUALITY_SIMULATOR_AUDIT.md",
            "106_AI_AGENT_DECISION_IMPROVEMENT_PLAN.md",
        ]:
            assert "postgresql://" not in _r(name)


class TestServiceImport:
    def test_simulator_service(self):
        from core.services.agent_quality_simulator_service import (
            AgentQualitySimulatorService,
        )

        assert AgentQualitySimulatorService is not None

    def test_schemas(self):
        from core.schemas.agent_quality_simulator import (
            AgentQualityReport,
            AgentScenario,
            AgentScenarioResult,
        )

        assert AgentScenario is not None
        assert AgentScenarioResult is not None
        assert AgentQualityReport is not None
