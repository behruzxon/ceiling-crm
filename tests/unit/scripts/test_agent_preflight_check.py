"""Tests for agent preflight check script."""
from __future__ import annotations

import os
from unittest.mock import patch

from scripts.agent_preflight_check import run_preflight


def _env(**flags: str):
    """Patch environment with given flags, clear all agent flags first."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_")}
    clean.update(flags)
    return patch.dict(os.environ, clean, clear=True)


class TestAllOff:
    def test_all_off_green(self):
        with _env():
            r = run_preflight()
            assert r.status == "green"
            assert not r.errors
            assert not r.warnings

    def test_all_off_has_pass(self):
        with _env():
            r = run_preflight()
            assert any("off" in c.lower() for c in r.checks)


class TestLogOnly:
    def test_log_only_green(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY="true",
        ):
            r = run_preflight()
            assert r.status == "green"

    def test_log_only_false_yellow(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY="false",
        ):
            r = run_preflight()
            assert r.status == "yellow"


class TestCanaryMode:
    def test_canary_without_ids_red(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_MODE="canary",
            AGENT_EXECUTION_CANARY_USER_IDS="",
        ):
            r = run_preflight()
            assert r.status == "red"
            assert any("canary" in e.lower() for e in r.errors)

    def test_canary_with_ids_ok(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_MODE="canary",
            AGENT_EXECUTION_CANARY_USER_IDS="12345,67890",
        ):
            r = run_preflight()
            assert r.status != "red" or not any("canary" in e.lower() for e in r.errors)


class TestLiveSender:
    def test_live_sender_without_queue_red(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_LIVE_SENDER_ENABLED="true",
            AGENT_EXECUTION_QUEUE_ENABLED="false",
        ):
            r = run_preflight()
            assert r.status == "red"
            assert any("queue" in e.lower() for e in r.errors)

    def test_live_sender_with_queue_ok(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_LIVE_SENDER_ENABLED="true",
            AGENT_EXECUTION_QUEUE_ENABLED="true",
        ):
            r = run_preflight()
            assert not any("queue" in e.lower() for e in r.errors)


class TestAutoExecute:
    def test_auto_execute_without_sender_red(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true",
            AGENT_EXECUTION_LIVE_SENDER_ENABLED="false",
        ):
            r = run_preflight()
            assert r.status == "red"
            assert any("auto_execute" in e.lower() for e in r.errors)

    def test_auto_execute_with_sender_ok(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true",
            AGENT_EXECUTION_LIVE_SENDER_ENABLED="true",
            AGENT_EXECUTION_QUEUE_ENABLED="true",
        ):
            r = run_preflight()
            assert not any("auto_execute" in e.lower() for e in r.errors)


class TestAdminNotify:
    def test_admin_notify_without_group_yellow(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY="true",
            BOT_ADMIN_GROUP_ID="",
        ):
            r = run_preflight()
            assert r.status in ("yellow", "red")
            assert any("admin" in w.lower() for w in r.warnings)


class TestAIComposer:
    def test_ai_composer_without_key_yellow(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_AI_COMPOSER_ENABLED="true",
            OPENAI_API_KEY="",
        ):
            r = run_preflight()
            assert any("openai" in w.lower() for w in r.warnings)

    def test_ai_composer_with_key_no_warn(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_AI_COMPOSER_ENABLED="true",
            OPENAI_API_KEY="sk-test-not-real",
        ):
            r = run_preflight()
            assert not any("openai" in w.lower() for w in r.warnings)


class TestFullLiveWarning:
    def test_full_live_yellow(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_MODE="live",
            AGENT_EXECUTION_LIVE_SENDER_ENABLED="true",
            AGENT_EXECUTION_QUEUE_ENABLED="true",
            AGENT_EXECUTION_AUTO_EXECUTE_APPROVED="true",
        ):
            r = run_preflight()
            assert any("live" in w.lower() for w in r.warnings)


class TestNoSecretPrinted:
    def test_no_key_in_output(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            OPENAI_API_KEY="sk-super-secret-key-12345",
            AGENT_AI_COMPOSER_ENABLED="true",
        ):
            r = run_preflight()
            all_text = " ".join(r.checks + r.warnings + r.errors)
            assert "sk-super-secret" not in all_text
            assert "12345" not in all_text


class TestSandboxChecks:
    def test_sandbox_enabled_logged(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_MODE="dry_run",
        ):
            r = run_preflight()
            assert any("sandbox" in c.lower() for c in r.checks)

    def test_queue_enabled_logged(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_QUEUE_ENABLED="true",
        ):
            r = run_preflight()
            assert any("queue" in c.lower() for c in r.checks)


class TestDryRunMode:
    def test_dry_run_safe(self):
        with _env(
            AGENT_RESPONSE_ORCHESTRATOR_ENABLED="true",
            AGENT_EXECUTION_SANDBOX_ENABLED="true",
            AGENT_EXECUTION_MODE="dry_run",
        ):
            r = run_preflight()
            assert r.status in ("green", "yellow")
            assert not r.errors
