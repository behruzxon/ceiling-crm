"""
Stage 5 APPROVED_LIVE_SEND Readiness Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only — no mutations, no sends, no secret printing.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


@dataclass
class LiveSendReadinessResult:
    ready: bool = True
    status: str = "green"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def _env_bool(key, default=False):
    val = os.environ.get(key, "").strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


def run_live_send_readiness() -> LiveSendReadinessResult:
    r = LiveSendReadinessResult()
    allow_live = _env_bool("AGENT_SETTINGS_ALLOW_LIVE_FLAGS")
    live_sender = _env_bool("AGENT_EXECUTION_LIVE_SENDER_ENABLED")
    auto_exec = _env_bool("AGENT_EXECUTION_AUTO_EXECUTE_APPROVED")
    queue = _env_bool("AGENT_EXECUTION_QUEUE_ENABLED")
    api_approval = _env_bool("AGENT_EXECUTION_API_APPROVAL_ENABLED")
    sandbox = _env_bool("AGENT_EXECUTION_SANDBOX_ENABLED")
    mode = os.environ.get("AGENT_EXECUTION_MODE", "log_only").strip().lower()

    if not allow_live:
        r.blockers.append("ALLOW_LIVE_FLAGS must be true")
    if not queue:
        r.blockers.append("Queue must be enabled")
    if not api_approval:
        r.blockers.append("API approval must be enabled")
    if not sandbox:
        r.blockers.append("Sandbox must be enabled")
    if mode == "live":
        r.blockers.append("Mode must be approval_required, not live")
    if live_sender and not queue:
        r.blockers.append("Live sender without queue")
    if auto_exec and not live_sender:
        r.blockers.append("Auto execute without live sender")

    if r.blockers:
        r.ready = False
        r.status = "red"
    elif not live_sender or not auto_exec:
        r.warnings.append("Live sender or auto execute not yet enabled")
        r.status = "yellow"

    if not r.blockers:
        r.checks.append("PASS: No critical blockers")
    return r


def print_result(r):
    icon = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}.get(r.status, "[?]")
    print(
        f"\n{icon} Stage 5 APPROVED_LIVE_SEND: {'READY' if r.ready else 'NOT READY'} ({r.status})\n"
    )
    for c in r.checks:
        print(f"  {c}")
    for w in r.warnings:
        print(f"  {w}")
    for b in r.blockers:
        print(f"  {b}")


if __name__ == "__main__":
    result = run_live_send_readiness()
    print_result(result)
    if not result.ready:
        sys.exit(1)
