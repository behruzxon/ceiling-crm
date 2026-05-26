"""Tests for Step AN — DRY_RUN docs existence."""
from __future__ import annotations

from pathlib import Path


class TestDocsExist:
    def test_preparation_doc(self):
        assert Path("docs/AI_AGENT_SYSTEM/34_STAGE_2_DRY_RUN_PREPARATION.md").exists()

    def test_test_script_doc(self):
        assert Path("docs/AI_AGENT_SYSTEM/35_STAGE_2_DRY_RUN_TEST_SCRIPT.md").exists()

    def test_observation_template(self):
        assert Path("docs/AI_AGENT_SYSTEM/36_STAGE_2_DRY_RUN_OBSERVATION_TEMPLATE.md").exists()


class TestDocsContent:
    def test_preparation_has_passfail(self):
        text = Path("docs/AI_AGENT_SYSTEM/34_STAGE_2_DRY_RUN_PREPARATION.md").read_text(encoding="utf-8")
        assert "PASS" in text and "FAIL" in text

    def test_preparation_has_rollback(self):
        text = Path("docs/AI_AGENT_SYSTEM/34_STAGE_2_DRY_RUN_PREPARATION.md").read_text(encoding="utf-8")
        assert "rollback" in text.lower() or "OFF" in text

    def test_test_script_has_scenarios(self):
        text = Path("docs/AI_AGENT_SYSTEM/35_STAGE_2_DRY_RUN_TEST_SCRIPT.md").read_text(encoding="utf-8")
        assert "qancha" in text.lower() or "scenario" in text.lower()

    def test_template_has_date(self):
        text = Path("docs/AI_AGENT_SYSTEM/36_STAGE_2_DRY_RUN_OBSERVATION_TEMPLATE.md").read_text(encoding="utf-8")
        assert "date" in text.lower() or "Date" in text
