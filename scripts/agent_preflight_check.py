"""
Agent Preflight Check
~~~~~~~~~~~~~~~~~~~~~
Validates agent feature flag configuration before rollout.
Read-only — no DB mutations, no sends, no secret printing.

Usage:
    python scripts/agent_preflight_check.py
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    status: str = "green"  # green / yellow / red
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip().lower()


def _env_bool(key: str, default: bool = False) -> bool:
    val = _env(key)
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    if val == "":
        return default
    return default


def run_preflight() -> CheckResult:
    result = CheckResult()

    # ── Stage detection ──────────────────────────────────────────────
    orchestrator_enabled = _env_bool("AGENT_RESPONSE_ORCHESTRATOR_ENABLED")
    orchestrator_log_only = _env_bool("AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY", True)
    sandbox_enabled = _env_bool("AGENT_EXECUTION_SANDBOX_ENABLED")
    execution_mode = _env("AGENT_EXECUTION_MODE", "log_only")
    queue_enabled = _env_bool("AGENT_EXECUTION_QUEUE_ENABLED")
    live_sender = _env_bool("AGENT_EXECUTION_LIVE_SENDER_ENABLED")
    auto_execute = _env_bool("AGENT_EXECUTION_AUTO_EXECUTE_APPROVED")
    canary_ids = _env("AGENT_EXECUTION_CANARY_USER_IDS")
    admin_notify = _env_bool("AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY")
    admin_group = _env("BOT_ADMIN_GROUP_ID")
    ai_composer = _env_bool("AGENT_AI_COMPOSER_ENABLED")
    openai_key_present = bool(_env("OPENAI_API_KEY"))

    # ── All off → green ──────────────────────────────────────────────
    if not orchestrator_enabled and not sandbox_enabled:
        result.checks.append("PASS: All agent flags off — safe")
        return result

    # ── Log only check ───────────────────────────────────────────────
    if orchestrator_enabled and orchestrator_log_only:
        result.checks.append("PASS: Orchestrator LOG_ONLY — no user impact")

    if orchestrator_enabled and not orchestrator_log_only:
        result.warnings.append(
            "WARN: Orchestrator LOG_ONLY=false — orchestrator can influence responses"
        )
        result.status = "yellow"

    # ── Canary mode without IDs ──────────────────────────────────────
    if execution_mode == "canary" and not canary_ids:
        result.errors.append(
            "FAIL: AGENT_EXECUTION_MODE=canary but CANARY_USER_IDS empty"
        )
        result.status = "red"

    # ── Live sender without queue ────────────────────────────────────
    if live_sender and not queue_enabled:
        result.errors.append(
            "FAIL: LIVE_SENDER enabled but QUEUE disabled — "
            "approved records won't be created"
        )
        result.status = "red"

    # ── Auto execute without live sender ─────────────────────────────
    if auto_execute and not live_sender:
        result.errors.append(
            "FAIL: AUTO_EXECUTE_APPROVED=true but LIVE_SENDER disabled"
        )
        result.status = "red"

    # ── Admin notify without admin group ─────────────────────────────
    if admin_notify and not admin_group:
        result.warnings.append(
            "WARN: APPROVAL_ADMIN_NOTIFY=true but BOT_ADMIN_GROUP_ID not set"
        )
        if result.status == "green":
            result.status = "yellow"

    # ── AI composer without OpenAI key ───────────────────────────────
    if ai_composer and not openai_key_present:
        result.warnings.append(
            "WARN: AI_COMPOSER enabled but OPENAI_API_KEY not set — "
            "will fallback to deterministic"
        )
        if result.status == "green":
            result.status = "yellow"

    # ── Live mode safety ─────────────────────────────────────────────
    if execution_mode == "live" and live_sender and auto_execute:
        result.warnings.append(
            "WARN: Full LIVE mode — agent can send messages autonomously"
        )
        if result.status == "green":
            result.status = "yellow"

    # ── Sandbox enabled check ────────────────────────────────────────
    if sandbox_enabled:
        result.checks.append(f"PASS: Sandbox enabled, mode={execution_mode}")

    if queue_enabled:
        result.checks.append("PASS: Execution queue enabled")

    if live_sender:
        result.checks.append("PASS: Live sender enabled")

    if not result.errors and not result.warnings:
        result.checks.append("PASS: All checks passed")

    return result


def print_result(result: CheckResult) -> None:
    status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(
        result.status, "⚪"
    )
    print(f"\n{status_icon} Agent Preflight: {result.status.upper()}\n")
    for c in result.checks:
        print(f"  {c}")
    for w in result.warnings:
        print(f"  {w}")
    for e in result.errors:
        print(f"  {e}")
    print()


if __name__ == "__main__":
    result = run_preflight()
    print_result(result)
    if result.status == "red":
        sys.exit(1)
