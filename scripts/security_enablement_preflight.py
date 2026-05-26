#!/usr/bin/env python3
"""
Security Enablement Preflight Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only check of security feature flags. No mutations, no secrets printed.

Usage:
    python scripts/security_enablement_preflight.py
    python scripts/security_enablement_preflight.py --stage S3
    python scripts/security_enablement_preflight.py --json
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key, "").strip()
    if val.isdigit():
        return int(val)
    return default


def gather_settings() -> dict:
    return {
        "app_env": os.environ.get("APP_ENV", "development"),
        "admin_rbac_enabled": _env_bool("ADMIN_RBAC_ENABLED", False),
        "admin_db_rbac_enabled": _env_bool("ADMIN_DB_RBAC_ENABLED", False),
        "admin_db_rbac_fallback_to_env": _env_bool("ADMIN_DB_RBAC_FALLBACK_TO_ENV", True),
        "admin_session_auth_enabled": _env_bool("ADMIN_SESSION_AUTH_ENABLED", False),
        "admin_session_secure_cookie": _env_bool("ADMIN_SESSION_SECURE_COOKIE", True),
        "admin_csrf_enabled": _env_bool("ADMIN_CSRF_ENABLED", False),
        "admin_security_actions_enabled": _env_bool("ADMIN_SECURITY_ACTIONS_ENABLED", False),
        "admin_security_action_audit_enabled": _env_bool("ADMIN_SECURITY_ACTION_AUDIT_ENABLED", True),
        "admin_ip_rules_enabled": _env_bool("ADMIN_IP_RULES_ENABLED", False),
        "admin_ip_block_enforcement_enabled": _env_bool("ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED", False),
        "admin_login_max_attempts": _env_int("ADMIN_LOGIN_MAX_ATTEMPTS", 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Security enablement preflight check")
    parser.add_argument("--stage", default="", help="Target stage (S0-S7)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    from core.services.security_enablement_service import SecurityEnablementService
    svc = SecurityEnablementService

    settings = gather_settings()
    has_secret = bool(os.environ.get("APP_SECRET_KEY", ""))

    report = svc.run_preflight(
        settings=settings,
        target_stage=args.stage,
        has_db_owner=False,
        has_secret_key=has_secret,
    )

    if args.json:
        from dataclasses import asdict
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
        return 0 if report.can_proceed else 1

    print(f"Security Enablement Preflight")
    print(f"Stage: {report.stage} — {report.stage_description}")
    print(f"Overall: {report.overall.upper()}")
    print()

    for check in report.checks:
        tag = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}.get(check.status, "[??]")
        print(f"  {tag} {check.name}: {check.message}")

    if report.blockers:
        print()
        print("BLOCKERS:")
        for b in report.blockers:
            print(f"  [FAIL] {b}")

    if report.warnings:
        print()
        print("WARNINGS:")
        for w in report.warnings:
            print(f"  [WARN] {w}")

    if report.can_proceed:
        print()
        print("[OK] Preflight passed — safe to proceed")
    else:
        print()
        print("[FAIL] Preflight FAILED — fix blockers before proceeding")

    return 0 if report.can_proceed else 1


if __name__ == "__main__":
    sys.exit(main())
