#!/usr/bin/env python3
"""
Final UI + Stage 1 Readiness Check — read-only.
No DB mutation, no secrets printed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_GREEN = "[OK]"
_YELLOW = "[WARN]"
_RED = "[FAIL]"


def check_critical_docs() -> list[tuple[str, str, str]]:
    results = []
    docs = [
        "docs/AI_AGENT_SYSTEM/53_NEXT_SESSION_STAGE_1_APPLY.md",
        "docs/AI_AGENT_SYSTEM/82_STAGE_1_GO_NO_GO_CHECKLIST.md",
        "docs/AI_AGENT_SYSTEM/83_PRODUCTION_RISK_REGISTER.md",
        "docs/AI_AGENT_SYSTEM/90_FINAL_UI_QA_STAGE_1_PREP.md",
    ]
    for doc in docs:
        if Path(doc).exists():
            results.append((_GREEN, doc.split("/")[-1], "exists"))
        else:
            results.append((_RED, doc.split("/")[-1], "MISSING"))
    return results


def check_templates() -> list[tuple[str, str, str]]:
    results = []
    templates = [
        "base.html", "login.html", "dashboard.html", "leads.html",
        "pipeline.html", "analytics.html", "agent.html",
        "crm_contacts.html", "crm_contact_detail.html",
        "crm_campaigns.html", "security.html",
    ]
    tpl_dir = Path("apps/web/templates")
    for name in templates:
        path = tpl_dir / name
        if path.exists():
            results.append((_GREEN, name, "exists"))
        else:
            results.append((_RED, name, "MISSING"))
    return results


def check_login_no_sidebar() -> list[tuple[str, str, str]]:
    login = Path("apps/web/templates/login.html")
    if not login.exists():
        return [(_RED, "login sidebar check", "login.html missing")]
    content = login.read_text(encoding="utf-8")
    if "vp-sidebar" in content:
        return [(_RED, "login sidebar leak", "vp-sidebar found in login.html")]
    if 'extends "base.html"' in content:
        return [(_RED, "login extends base", "login.html extends base.html")]
    return [(_GREEN, "login standalone", "no sidebar leak")]


def check_sidebar_routes() -> list[tuple[str, str, str]]:
    base = Path("apps/web/templates/base.html")
    if not base.exists():
        return [(_RED, "sidebar routes", "base.html missing")]
    content = base.read_text(encoding="utf-8")
    results = []
    required = [
        ("/dashboard", "Dashboard"),
        ("/crm", "CRM/Inbox"),
        ("/crm/campaigns", "Campaigns"),
        ("/agent", "Agent"),
        ("/admin/security", "Security"),
    ]
    for route, label in required:
        if route in content:
            results.append((_GREEN, f"sidebar {label}", f"{route} present"))
        else:
            results.append((_RED, f"sidebar {label}", f"{route} MISSING"))
    return results


def check_dangerous_flags() -> list[tuple[str, str, str]]:
    results = []
    try:
        from shared.config.settings import BusinessSettings
        fields = BusinessSettings.model_fields
        flags = [
            "agent_followups_enabled",
            "agent_execution_live_sender_enabled",
            "agent_execution_auto_execute_approved",
            "crm_operator_reply_enabled",
            "crm_campaign_send_enabled",
            "crm_daily_report_delivery_enabled",
            "admin_session_auth_enabled",
            "admin_security_actions_enabled",
            "admin_ip_block_enforcement_enabled",
        ]
        for flag in flags:
            if flag in fields:
                default = fields[flag].default
                if default is False:
                    results.append((_GREEN, flag, f"default={default}"))
                else:
                    results.append((_RED, flag, f"default={default} — DANGEROUS"))
            else:
                results.append((_YELLOW, flag, "not found in settings"))
    except Exception as e:
        results.append((_RED, "settings import", str(e)[:120]))
    return results


def check_no_secrets_in_templates() -> list[tuple[str, str, str]]:
    results = []
    tpl_dir = Path("apps/web/templates")
    if not tpl_dir.exists():
        return [(_RED, "templates dir", "missing")]
    for tpl in tpl_dir.glob("*.html"):
        content = tpl.read_text(encoding="utf-8")
        for pattern in ["sk-", "bot_token", "session_id_hash"]:
            if pattern in content.lower():
                results.append((_RED, tpl.name, f"contains '{pattern}'"))
                break
    if not results:
        results.append((_GREEN, "template secrets", "none found"))
    return results


def main() -> int:
    print("Final UI + Stage 1 Readiness Check")
    print("=" * 50)
    all_results: list[tuple[str, str, str]] = []

    sections = [
        ("Critical Docs", check_critical_docs),
        ("Templates", check_templates),
        ("Login Standalone", check_login_no_sidebar),
        ("Sidebar Routes", check_sidebar_routes),
        ("Dangerous Flags", check_dangerous_flags),
        ("Secrets in Templates", check_no_secrets_in_templates),
    ]

    for title, fn in sections:
        print(f"\n-- {title} --")
        for r in fn():
            print(f"  {r[0]} {r[1]}: {r[2]}")
            all_results.append(r)

    reds = sum(1 for r in all_results if r[0] == _RED)
    yellows = sum(1 for r in all_results if r[0] == _YELLOW)
    greens = sum(1 for r in all_results if r[0] == _GREEN)

    print(f"\nSummary: {greens} OK, {yellows} WARN, {reds} FAIL")
    if reds > 0:
        print(f"{_RED} NOT ready — fix {reds} failures")
        return 1
    elif yellows > 0:
        print(f"{_YELLOW} CONDITIONAL GO — review {yellows} warnings")
        return 0
    else:
        print(f"{_GREEN} READY for Stage 1 LOG_ONLY apply")
        return 0


if __name__ == "__main__":
    sys.exit(main())
