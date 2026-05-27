"""Tests for Stage 4 APPROVAL_REQUIRED readiness check."""

from __future__ import annotations

import os
from unittest.mock import patch

from scripts.agent_stage4_approval_readiness_check import run_approval_readiness


def _env(**flags):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_")}
    clean.update(flags)
    return patch.dict(os.environ, clean, clear=True)


class TestBlockers:
    def test_queue_disabled_red(self):
        with _env(AGENT_EXECUTION_QUEUE_ENABLED="false"):
            assert not run_approval_readiness().ready

    def test_api_disabled_red(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true", AGENT_EXECUTION_API_APPROVAL_ENABLED="false"
        ):
            assert not run_approval_readiness().ready

    def test_live_sender_red(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true",
            AGENT_EXECUTION_API_APPROVAL_ENABLED="true",
            AGENT_EXECUTION_LIVE_SENDER_ENABLED="true",
        ):
            assert not run_approval_readiness().ready

    def test_auto_execute_red(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true",
            AGENT_EXECUTION_API_APPROVAL_ENABLED="true",
            AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true",
        ):
            assert not run_approval_readiness().ready

    def test_mode_live_red(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true",
            AGENT_EXECUTION_API_APPROVAL_ENABLED="true",
            AGENT_EXECUTION_MODE="live",
        ):
            assert not run_approval_readiness().ready


class TestClean:
    def test_all_correct_green(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true", AGENT_EXECUTION_API_APPROVAL_ENABLED="true"
        ):
            r = run_approval_readiness()
            assert r.ready and r.status in ("green", "yellow")


class TestWarnings:
    def test_allow_live_warning(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true",
            AGENT_EXECUTION_API_APPROVAL_ENABLED="true",
            AGENT_SETTINGS_ALLOW_LIVE_FLAGS="true",
        ):
            assert any("live" in w.lower() for w in run_approval_readiness().warnings)


class TestNoSecrets:
    def test_clean(self):
        with _env(
            AGENT_EXECUTION_QUEUE_ENABLED="true",
            AGENT_EXECUTION_API_APPROVAL_ENABLED="true",
            OPENAI_API_KEY="sk-secret",
        ):
            r = run_approval_readiness()
            assert "sk-secret" not in " ".join(r.checks + r.warnings + r.blockers)
