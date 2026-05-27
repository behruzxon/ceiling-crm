"""Tests for Stage 1 LOG_ONLY readiness check script."""

from __future__ import annotations

import os
from unittest.mock import patch

from scripts.agent_stage1_readiness_check import run_stage1_readiness


def _env(**flags: str):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_")}
    clean.update(flags)
    return patch.dict(os.environ, clean, clear=True)


class TestAllOff:
    def test_ready(self):
        with _env():
            r = run_stage1_readiness()
            assert r.ready is True

    def test_no_red(self):
        with _env():
            r = run_stage1_readiness()
            assert r.status in ("green", "yellow")


class TestLogOnlyActive:
    def test_ready(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY="true",
            AGENT_RUNTIME_SETTINGS_ENABLED="true",
            AGENT_SETTINGS_MUTATION_ENABLED="true",
        ):
            r = run_stage1_readiness()
            assert r.status == "green"
            assert r.ready is True


class TestBlockers:
    def test_followups_enabled_red(self):
        with _env(AGENT_FOLLOWUPS_ENABLED="true"):
            r = run_stage1_readiness()
            assert r.status == "red"
            assert not r.ready

    def test_catalog_followup_red(self):
        with _env(AGENT_CATALOG_FOLLOWUP_ENABLED="true"):
            r = run_stage1_readiness()
            assert not r.ready

    def test_live_sender_red(self):
        with _env(AGENT_EXECUTION_LIVE_SENDER_ENABLED="true"):
            r = run_stage1_readiness()
            assert r.status == "red"

    def test_auto_execute_red(self):
        with _env(AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true"):
            r = run_stage1_readiness()
            assert r.status == "red"

    def test_orch_log_only_false_red(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY="false",
        ):
            r = run_stage1_readiness()
            assert r.status == "red"

    def test_mode_live_red(self):
        with _env(AGENT_EXECUTION_MODE="live"):
            r = run_stage1_readiness()
            assert r.status == "red"

    def test_admin_escalation_red(self):
        with _env(AGENT_ADMIN_ESCALATION_ENABLED="true"):
            r = run_stage1_readiness()
            assert not r.ready


class TestWarnings:
    def test_canary_mode_warning(self):
        with _env(AGENT_EXECUTION_MODE="canary"):
            r = run_stage1_readiness()
            assert len(r.warnings) > 0

    def test_runtime_disabled_warning(self):
        with _env(AGENT_RUNTIME_SETTINGS_ENABLED="false"):
            r = run_stage1_readiness()
            assert any("runtime" in w.lower() for w in r.warnings)

    def test_mutation_disabled_warning(self):
        with _env(AGENT_SETTINGS_MUTATION_ENABLED="false"):
            r = run_stage1_readiness()
            assert any("mutation" in w.lower() for w in r.warnings)


class TestNoSecrets:
    def test_no_key_in_output(self):
        with _env(OPENAI_API_KEY="sk-super-secret"):
            r = run_stage1_readiness()
            all_text = " ".join(r.checks + r.warnings + r.blockers)
            assert "sk-super" not in all_text

    def test_no_token_in_output(self):
        with _env(BOT_TOKEN="123:ABC"):
            r = run_stage1_readiness()
            all_text = " ".join(r.checks + r.warnings + r.blockers)
            assert "123:ABC" not in all_text


class TestCorrectLogOnly:
    def test_no_red(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY="true",
            AGENT_LEAD_SIGNAL_ENABLED="true",
            AGENT_DECISION_ENGINE_ENABLED="true",
        ):
            r = run_stage1_readiness()
            assert r.status != "red"
            assert r.ready is True
