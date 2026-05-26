#!/usr/bin/env python3
"""
Platform Readiness Audit — read-only checks.
No DB mutation, no secrets printed.
"""
from __future__ import annotations
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_GREEN = "[OK]"
_YELLOW = "[WARN]"
_RED = "[FAIL]"


def check_imports() -> list[tuple[str, str, str]]:
    results = []
    modules = [
        ("apps.bot.main", "Bot main"),
        ("apps.scheduler.main", "Scheduler main"),
        ("apps.api.main", "API main"),
        ("apps.web.main", "Web main"),
        ("core.services.admin_rbac_service", "RBAC service"),
        ("core.services.admin_auth_service", "Auth service"),
        ("core.services.crm_campaign_service", "Campaign service"),
        ("core.services.crm_contact_merge_service", "Merge service"),
        ("core.services.security_enablement_service", "Enablement service"),
    ]
    for mod_path, label in modules:
        try:
            importlib.import_module(mod_path)
            results.append((_GREEN, label, "importable"))
        except Exception as e:
            results.append((_RED, label, str(e)[:100]))
    return results


def check_docs() -> list[tuple[str, str, str]]:
    results = []
    docs = [
        "docs/AI_AGENT_SYSTEM/69_SECURITY_ENABLEMENT_PLAN.md",
        "docs/AI_AGENT_SYSTEM/70_SECURITY_PREFLIGHT_RUNBOOK.md",
        "docs/AI_AGENT_SYSTEM/71_SECURITY_ROLLBACK_CARD.md",
        "docs/AI_AGENT_SYSTEM/72_SECURITY_STAGING_TEST_SCRIPT.md",
        "docs/AI_AGENT_SYSTEM/81_PLATFORM_READINESS_AUDIT.md",
        "docs/AI_AGENT_SYSTEM/82_STAGE_1_GO_NO_GO_CHECKLIST.md",
        "docs/AI_AGENT_SYSTEM/83_PRODUCTION_RISK_REGISTER.md",
    ]
    for doc in docs:
        if Path(doc).exists():
            results.append((_GREEN, doc.split("/")[-1], "exists"))
        else:
            results.append((_YELLOW, doc.split("/")[-1], "missing"))
    return results


def check_dangerous_flags() -> list[tuple[str, str, str]]:
    results = []
    try:
        from shared.config.settings import BusinessSettings
        fields = BusinessSettings.model_fields
        dangerous_off = [
            "agent_followups_enabled", "agent_execution_live_sender_enabled",
            "agent_execution_auto_execute_approved", "crm_operator_reply_enabled",
            "crm_campaign_send_enabled", "crm_daily_report_delivery_enabled",
            "admin_session_auth_enabled", "admin_csrf_enabled",
            "admin_db_rbac_enabled", "admin_security_actions_enabled",
            "admin_ip_block_enforcement_enabled", "crm_contact_merge_enabled",
        ]
        for flag in dangerous_off:
            if flag in fields:
                default = fields[flag].default
                if default is False:
                    results.append((_GREEN, flag, f"default={default}"))
                else:
                    results.append((_RED, flag, f"default={default} — DANGEROUS"))
            else:
                results.append((_YELLOW, flag, "not found"))
    except Exception as e:
        results.append((_RED, "settings import", str(e)[:100]))
    return results


def check_migrations() -> list[tuple[str, str, str]]:
    mig_dir = Path("infrastructure/database/migrations/versions")
    files = list(mig_dir.glob("*.py")) if mig_dir.exists() else []
    count = len(files)
    if count >= 40:
        return [(_GREEN, "migrations", f"{count} files found")]
    elif count >= 20:
        return [(_YELLOW, "migrations", f"{count} files — check chain")]
    return [(_RED, "migrations", f"only {count} files")]


def main() -> int:
    print("Platform Readiness Audit")
    print("=" * 50)
    all_results: list[tuple[str, str, str]] = []

    print("\n-- Import Smoke --")
    for r in check_imports():
        print(f"  {r[0]} {r[1]}: {r[2]}")
        all_results.append(r)

    print("\n-- Docs --")
    for r in check_docs():
        print(f"  {r[0]} {r[1]}: {r[2]}")
        all_results.append(r)

    print("\n-- Dangerous Flags --")
    for r in check_dangerous_flags():
        print(f"  {r[0]} {r[1]}: {r[2]}")
        all_results.append(r)

    print("\n-- Migrations --")
    for r in check_migrations():
        print(f"  {r[0]} {r[1]}: {r[2]}")
        all_results.append(r)

    reds = sum(1 for r in all_results if r[0] == _RED)
    yellows = sum(1 for r in all_results if r[0] == _YELLOW)
    greens = sum(1 for r in all_results if r[0] == _GREEN)

    print(f"\nSummary: {greens} OK, {yellows} WARN, {reds} FAIL")
    if reds > 0:
        print(f"{_RED} Platform NOT ready — fix {reds} failures")
        return 1
    elif yellows > 0:
        print(f"{_YELLOW} CONDITIONAL GO — review {yellows} warnings")
        return 0
    else:
        print(f"{_GREEN} Platform READY")
        return 0


if __name__ == "__main__":
    sys.exit(main())
