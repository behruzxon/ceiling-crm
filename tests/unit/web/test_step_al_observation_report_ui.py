"""Tests for Step AL — Stage 1 Observation Report UI."""
from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")


class TestObservationPanel:
    def test_panel_present(self):
        assert "observationPanel" in _TEMPLATE

    def test_observation_result_container(self):
        assert "observationResult" in _TEMPLATE

    def test_load_function(self):
        assert "loadObservationReport" in _TEMPLATE

    def test_pass_fail_badge(self):
        assert "PASS" in _TEMPLATE
        assert "FAIL" in _TEMPLATE

    def test_no_send_display(self):
        assert "No-send" in _TEMPLATE or "no_send" in _TEMPLATE

    def test_recommendations_display(self):
        assert "recommendations" in _TEMPLATE

    def test_no_secrets(self):
        assert "api_key" not in _TEMPLATE.lower()
        assert "bot_token" not in _TEMPLATE.lower()

    def test_stage1_label(self):
        assert "Stage 1 Observation" in _TEMPLATE


class TestNonRegression:
    def test_control_center_present(self):
        assert "Control Center" in _TEMPLATE

    def test_status_header_present(self):
        assert "agentStatusHeader" in _TEMPLATE

    def test_stage_timeline_present(self):
        assert "stageTimeline" in _TEMPLATE

    def test_presets_present(self):
        assert "Rollout Presets" in _TEMPLATE

    def test_settings_present(self):
        assert "Settings Control" in _TEMPLATE
