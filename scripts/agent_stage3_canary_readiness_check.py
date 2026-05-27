"""
Stage 3 CANARY Readiness Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies environment is safe for CANARY (first real send to test users).
Read-only — no mutations, no sends, no secret printing.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


@dataclass
class CanaryReadinessResult:
    ready: bool = True
    status: str = "green"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    canary_id_count: int = 0


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


def run_canary_readiness() -> CanaryReadinessResult:
    r = CanaryReadinessResult()

    canary_ids = os.environ.get("AGENT_EXECUTION_CANARY_USER_IDS", "").strip()
    r.canary_id_count = len([x for x in canary_ids.split(",") if x.strip()]) if canary_ids else 0

    if r.canary_id_count == 0:
        r.blockers.append("CANARY_USER_IDS not configured")

    live_sender = _env_bool("AGENT_EXECUTION_LIVE_SENDER_ENABLED")
    auto_exec = _env_bool("AGENT_EXECUTION_AUTO_EXECUTE_APPROVED")
    mode = os.environ.get("AGENT_EXECUTION_MODE", "log_only").strip().lower()
    allow_live = _env_bool("AGENT_SETTINGS_ALLOW_LIVE_FLAGS")
    followups = _env_bool("AGENT_FOLLOWUPS_ENABLED")
    admin_esc = _env_bool("AGENT_ADMIN_ESCALATION_ENABLED")

    if live_sender:
        r.blockers.append("Live sender must be OFF for initial canary")
    if auto_exec:
        r.blockers.append("Auto execute must be OFF")
    if mode == "live":
        r.blockers.append("Execution mode must not be LIVE")

    if followups:
        r.warnings.append("Followups enabled — disable for initial canary")
    if admin_esc:
        r.warnings.append("Admin escalation enabled — disable for initial canary")
    if allow_live:
        r.warnings.append("Allow live flags is ON — ensure intentional")

    if r.blockers:
        r.ready = False
        r.status = "red"
    elif r.warnings:
        r.status = "yellow"

    if r.canary_id_count > 0:
        r.checks.append(f"PASS: {r.canary_id_count} canary user(s) configured")
    if not r.blockers:
        r.checks.append("PASS: No critical blockers")

    return r


def print_result(r: CanaryReadinessResult) -> None:
    icon = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}.get(r.status, "[?]")
    label = "READY" if r.ready else "NOT READY"
    print(f"\n{icon} Stage 3 CANARY: {label} ({r.status})\n")
    for c in r.checks:
        print(f"  {c}")
    for w in r.warnings:
        print(f"  {w}")
    for b in r.blockers:
        print(f"  {b}")
    print()


if __name__ == "__main__":
    result = run_canary_readiness()
    print_result(result)
    if not result.ready:
        sys.exit(1)
