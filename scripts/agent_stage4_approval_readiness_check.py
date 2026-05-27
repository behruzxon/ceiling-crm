"""
Stage 4 APPROVAL_REQUIRED Readiness Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies environment is safe for APPROVAL_REQUIRED (human-in-the-loop).
Read-only — no mutations, no sends, no secret printing.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


@dataclass
class ApprovalReadinessResult:
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


def run_approval_readiness() -> ApprovalReadinessResult:
    r = ApprovalReadinessResult()

    queue = _env_bool("AGENT_EXECUTION_QUEUE_ENABLED")
    api_approval = _env_bool("AGENT_EXECUTION_API_APPROVAL_ENABLED")
    live_sender = _env_bool("AGENT_EXECUTION_LIVE_SENDER_ENABLED")
    auto_exec = _env_bool("AGENT_EXECUTION_AUTO_EXECUTE_APPROVED")
    mode = os.environ.get("AGENT_EXECUTION_MODE", "log_only").strip().lower()
    allow_live = _env_bool("AGENT_SETTINGS_ALLOW_LIVE_FLAGS")

    if not queue:
        r.blockers.append("Execution queue must be enabled")
    if not api_approval:
        r.blockers.append("API approval must be enabled")
    if live_sender:
        r.blockers.append("Live sender must be OFF")
    if auto_exec:
        r.blockers.append("Auto execute must be OFF")
    if mode == "live":
        r.blockers.append("Execution mode must not be LIVE")

    if allow_live:
        r.warnings.append("Allow live flags is ON — ensure intentional")

    if r.blockers:
        r.ready = False
        r.status = "red"
    elif r.warnings:
        r.status = "yellow"

    if queue:
        r.checks.append("PASS: Queue enabled")
    if api_approval:
        r.checks.append("PASS: API approval enabled")
    if not r.blockers:
        r.checks.append("PASS: No critical blockers")

    return r


def print_result(r: ApprovalReadinessResult) -> None:
    icon = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}.get(r.status, "[?]")
    label = "READY" if r.ready else "NOT READY"
    print(f"\n{icon} Stage 4 APPROVAL_REQUIRED: {label} ({r.status})\n")
    for c in r.checks:
        print(f"  {c}")
    for w in r.warnings:
        print(f"  {w}")
    for b in r.blockers:
        print(f"  {b}")
    print()


if __name__ == "__main__":
    result = run_approval_readiness()
    print_result(result)
    if not result.ready:
        sys.exit(1)
