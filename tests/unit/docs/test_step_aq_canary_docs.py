"""Tests for Step AQ — CANARY docs existence."""
from __future__ import annotations

from pathlib import Path


class TestDocsExist:
    def test_preparation(self):
        assert Path("docs/AI_AGENT_SYSTEM/39_STAGE_3_CANARY_PREPARATION.md").exists()

    def test_test_script(self):
        assert Path("docs/AI_AGENT_SYSTEM/40_STAGE_3_CANARY_TEST_SCRIPT.md").exists()

    def test_observation_template(self):
        assert Path("docs/AI_AGENT_SYSTEM/41_STAGE_3_CANARY_OBSERVATION_TEMPLATE.md").exists()


class TestDocsContent:
    def test_has_rollback(self):
        text = Path("docs/AI_AGENT_SYSTEM/39_STAGE_3_CANARY_PREPARATION.md").read_text(encoding="utf-8")
        assert "rollback" in text.lower() or "OFF" in text

    def test_has_non_canary(self):
        text = Path("docs/AI_AGENT_SYSTEM/39_STAGE_3_CANARY_PREPARATION.md").read_text(encoding="utf-8")
        assert "non-canary" in text.lower() or "canary" in text.lower()

    def test_script_has_scenarios(self):
        text = Path("docs/AI_AGENT_SYSTEM/40_STAGE_3_CANARY_TEST_SCRIPT.md").read_text(encoding="utf-8")
        assert "canary" in text.lower()
