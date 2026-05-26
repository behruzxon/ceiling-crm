"""Tests for Step AM — DRY_RUN Gate UI panel."""
from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")


class TestGatePanel:
    def test_panel_present(self):
        assert "dryrunGatePanel" in _TEMPLATE

    def test_gate_result_container(self):
        assert "gateResult" in _TEMPLATE

    def test_load_function(self):
        assert "loadDryrunGate" in _TEMPLATE

    def test_verdict_display(self):
        assert "verdict" in _TEMPLATE.lower()

    def test_readiness_score_display(self):
        assert "readiness_score" in _TEMPLATE

    def test_blocker_display(self):
        assert "BLOCKER" in _TEMPLATE

    def test_warning_display(self):
        assert "WARNING" in _TEMPLATE

    def test_recommendations_display(self):
        assert "recommendations" in _TEMPLATE

    def test_dryrun_help_text(self):
        assert "DRY_RUN" in _TEMPLATE

    def test_no_secrets(self):
        assert "api_key" not in _TEMPLATE.lower()
        assert "bot_token" not in _TEMPLATE.lower()


class TestNonRegression:
    def test_observation_panel(self):
        assert "observationPanel" in _TEMPLATE

    def test_control_center(self):
        assert "Control Center" in _TEMPLATE

    def test_presets(self):
        assert "Rollout Presets" in _TEMPLATE
