"""Tests for Stage 5 APPROVED_LIVE_SEND readiness check."""
from __future__ import annotations
import os
from unittest.mock import patch
from scripts.agent_stage5_live_send_readiness_check import run_live_send_readiness

def _env(**flags):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_")}
    clean.update(flags)
    return patch.dict(os.environ, clean, clear=True)

class TestBlockers:
    def test_allow_live_false_red(self):
        with _env(): assert not run_live_send_readiness().ready

    def test_queue_disabled_red(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true"):
            assert not run_live_send_readiness().ready

    def test_api_disabled_red(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true", AGENT_EXECUTION_QUEUE_ENABLED="true"):
            assert not run_live_send_readiness().ready

    def test_sandbox_disabled_red(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true", AGENT_EXECUTION_QUEUE_ENABLED="true",
                  AGENT_EXECUTION_API_APPROVAL_ENABLED="true"):
            assert not run_live_send_readiness().ready

    def test_mode_live_red(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true", AGENT_EXECUTION_QUEUE_ENABLED="true",
                  AGENT_EXECUTION_API_APPROVAL_ENABLED="true", AGENT_EXECUTION_SANDBOX_ENABLED="true",
                  AGENT_EXECUTION_MODE="live"):
            assert not run_live_send_readiness().ready

    def test_sender_without_queue_red(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true",
                  AGENT_EXECUTION_LIVE_SENDER_ENABLED="true"):
            assert not run_live_send_readiness().ready

    def test_auto_without_sender_red(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true", AGENT_EXECUTION_QUEUE_ENABLED="true",
                  AGENT_EXECUTION_API_APPROVAL_ENABLED="true", AGENT_EXECUTION_SANDBOX_ENABLED="true",
                  AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true"):
            assert not run_live_send_readiness().ready

class TestClean:
    def test_full_correct(self):
        with _env(AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true", AGENT_EXECUTION_QUEUE_ENABLED="true",
                  AGENT_EXECUTION_API_APPROVAL_ENABLED="true", AGENT_EXECUTION_SANDBOX_ENABLED="true",
                  AGENT_EXECUTION_LIVE_SENDER_ENABLED="true", AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true"):
            r = run_live_send_readiness()
            assert r.ready and r.status == "green"

class TestNoSecrets:
    def test_clean(self):
        with _env(OPENAI_API_KEY="sk-secret"):
            r = run_live_send_readiness()
            assert "sk-secret" not in " ".join(r.checks + r.warnings + r.blockers)
