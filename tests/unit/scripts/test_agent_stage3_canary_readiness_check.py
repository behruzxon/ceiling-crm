"""Tests for Stage 3 CANARY readiness check script."""

from __future__ import annotations

import os
from unittest.mock import patch

from scripts.agent_stage3_canary_readiness_check import run_canary_readiness


def _env(**flags: str):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_")}
    clean.update(flags)
    return patch.dict(os.environ, clean, clear=True)


class TestCanaryIDs:
    def test_missing_ids_red(self):
        with _env():
            r = run_canary_readiness()
            assert not r.ready
            assert r.status == "red"

    def test_with_ids_ok(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123,456"):
            r = run_canary_readiness()
            assert r.canary_id_count == 2

    def test_count_correct(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="1,2,3"):
            r = run_canary_readiness()
            assert r.canary_id_count == 3


class TestBlockers:
    def test_live_sender_red(self):
        with _env(
            AGENT_EXECUTION_CANARY_USER_IDS="123", AGENT_EXECUTION_LIVE_SENDER_ENABLED="true"
        ):
            r = run_canary_readiness()
            assert not r.ready

    def test_auto_execute_red(self):
        with _env(
            AGENT_EXECUTION_CANARY_USER_IDS="123", AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true"
        ):
            r = run_canary_readiness()
            assert not r.ready

    def test_mode_live_red(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123", AGENT_EXECUTION_MODE="live"):
            r = run_canary_readiness()
            assert not r.ready


class TestWarnings:
    def test_followups_warning(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123", AGENT_FOLLOWUPS_ENABLED="true"):
            r = run_canary_readiness()
            assert any("followup" in w.lower() for w in r.warnings)

    def test_escalation_warning(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123", AGENT_ADMIN_ESCALATION_ENABLED="true"):
            r = run_canary_readiness()
            assert any("escalation" in w.lower() for w in r.warnings)

    def test_allow_live_warning(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123", AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true"):
            r = run_canary_readiness()
            assert any("live" in w.lower() for w in r.warnings)


class TestClean:
    def test_green(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123"):
            r = run_canary_readiness()
            assert r.ready
            assert r.status in ("green", "yellow")

    def test_no_secret(self):
        with _env(AGENT_EXECUTION_CANARY_USER_IDS="123", OPENAI_API_KEY="sk-secret"):
            r = run_canary_readiness()
            all_text = " ".join(r.checks + r.warnings + r.blockers)
            assert "sk-secret" not in all_text
            assert "123" not in all_text or "1 canary" in all_text
