"""Tests for Step AH — Operator Training Pack UI elements."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")


class TestOperatorHelpLink:
    def test_help_link_present(self):
        assert "operatorHelpLink" in _TEMPLATE

    def test_qollanma_link(self):
        assert "Qo'llanma" in _TEMPLATE

    def test_rollback_link(self):
        assert "Rollback" in _TEMPLATE

    def test_no_secrets_in_help(self):
        assert "api_key" not in _TEMPLATE.lower()


class TestDocsExist:
    def test_training_pack(self):
        assert Path("docs/AI_AGENT_SYSTEM/26_OPERATOR_TRAINING_PACK.md").exists()

    def test_daily_checklist(self):
        assert Path("docs/AI_AGENT_SYSTEM/27_OPERATOR_DAILY_CHECKLIST.md").exists()

    def test_test_script(self):
        assert Path("docs/AI_AGENT_SYSTEM/28_STAGE_1_OPERATOR_TEST_SCRIPT.md").exists()

    def test_rollback_card(self):
        assert Path("docs/AI_AGENT_SYSTEM/29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md").exists()

    def test_glossary(self):
        assert Path("docs/AI_AGENT_SYSTEM/30_AGENT_TERMS_GLOSSARY.md").exists()


class TestNonRegression:
    def test_control_center_present(self):
        assert "Control Center" in _TEMPLATE

    def test_stage_timeline_present(self):
        assert "stageTimeline" in _TEMPLATE

    def test_status_header_present(self):
        assert "agentStatusHeader" in _TEMPLATE
