"""Tests for Step AT — APPROVAL_REQUIRED docs existence."""
from __future__ import annotations

from pathlib import Path


class TestDocsExist:
    def test_preparation(self):
        assert Path("docs/AI_AGENT_SYSTEM/44_STAGE_4_APPROVAL_REQUIRED_PREPARATION.md").exists()

    def test_test_script(self):
        assert Path("docs/AI_AGENT_SYSTEM/45_STAGE_4_APPROVAL_REQUIRED_TEST_SCRIPT.md").exists()

    def test_template(self):
        assert Path("docs/AI_AGENT_SYSTEM/46_STAGE_4_APPROVAL_REQUIRED_OBSERVATION_TEMPLATE.md").exists()

class TestContent:
    def test_rollback(self):
        t = Path("docs/AI_AGENT_SYSTEM/44_STAGE_4_APPROVAL_REQUIRED_PREPARATION.md").read_text(encoding="utf-8")
        assert "rollback" in t.lower() or "OFF" in t

    def test_auto_execute_off(self):
        t = Path("docs/AI_AGENT_SYSTEM/44_STAGE_4_APPROVAL_REQUIRED_PREPARATION.md").read_text(encoding="utf-8")
        assert "auto" in t.lower() and "false" in t.lower()

    def test_live_sender_off(self):
        t = Path("docs/AI_AGENT_SYSTEM/44_STAGE_4_APPROVAL_REQUIRED_PREPARATION.md").read_text(encoding="utf-8")
        assert "live" in t.lower() and "sender" in t.lower()
