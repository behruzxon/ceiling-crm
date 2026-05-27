"""
Stage 1 LOG_ONLY Readiness Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies the environment is safe for Stage 1 LOG_ONLY observation.
Read-only — no mutations, no sends, no secret printing.

Usage:
    python scripts/agent_stage1_readiness_check.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


@dataclass
class ReadinessResult:
    ready: bool = True
    status: str = "green"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


def run_stage1_readiness() -> ReadinessResult:
    r = ReadinessResult()

    followups = _env_bool("AGENT_FOLLOWUPS_ENABLED")
    catalog_fu = _env_bool("AGENT_CATALOG_FOLLOWUP_ENABLED")
    price_fu = _env_bool("AGENT_PRICE_FOLLOWUP_ENABLED")
    order_fu = _env_bool("AGENT_ORDER_FOLLOWUP_ENABLED")
    live_sender = _env_bool("AGENT_EXECUTION_LIVE_SENDER_ENABLED")
    auto_exec = _env_bool("AGENT_EXECUTION_AUTO_EXECUTE_APPROVED")
    orch_enabled = _env_bool("AGENT_RESPONSE_ORCHESTRATOR_ENABLED")
    orch_log_only = _env_bool("AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY", True)
    admin_esc = _env_bool("AGENT_ADMIN_ESCALATION_ENABLED")
    mode = os.environ.get("AGENT_EXECUTION_MODE", "log_only").strip().lower()
    runtime_enabled = _env_bool("AGENT_RUNTIME_SETTINGS_ENABLED")
    mutation_enabled = _env_bool("AGENT_SETTINGS_MUTATION_ENABLED")

    if followups or catalog_fu or price_fu or order_fu:
        r.blockers.append("Follow-ups enabled — must be false for LOG_ONLY")
    if live_sender:
        r.blockers.append("Live sender enabled — must be false")
    if auto_exec:
        r.blockers.append("Auto execute enabled — must be false")
    if not orch_log_only and orch_enabled:
        r.blockers.append("Orchestrator LOG_ONLY is false — must be true")
    if mode == "live":
        r.blockers.append("Execution mode is LIVE — must be log_only")
    if mode == "canary":
        r.warnings.append("Execution mode is CANARY — expected log_only for Stage 1")
    if admin_esc:
        r.blockers.append("Admin escalation enabled — must be false for LOG_ONLY")

    if not runtime_enabled:
        r.warnings.append("Runtime settings disabled — apply via UI won't work")
    if not mutation_enabled:
        r.warnings.append("Settings mutation disabled — preset apply via API won't work")

    if r.blockers:
        r.ready = False
        r.status = "red"
    elif r.warnings:
        r.status = "yellow"

    if not r.blockers:
        r.checks.append("PASS: No dangerous flags for LOG_ONLY")
    if orch_enabled and orch_log_only:
        r.checks.append("PASS: Orchestrator LOG_ONLY active")
    elif not orch_enabled:
        r.checks.append("INFO: Orchestrator not yet enabled — apply LOG_ONLY preset")

    return r


def print_result(r: ReadinessResult) -> None:
    icon = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}.get(r.status, "[?]")
    label = "READY" if r.ready else "NOT READY"
    print(f"\n{icon} Stage 1 LOG_ONLY: {label} ({r.status})\n")
    for c in r.checks:
        print(f"  {c}")
    for w in r.warnings:
        print(f"  {w}")
    for b in r.blockers:
        print(f"  {b}")
    print()


if __name__ == "__main__":
    result = run_stage1_readiness()
    print_result(result)
    if not result.ready:
        sys.exit(1)
