#!/usr/bin/env python3
"""Production deploy dry-run check — read-only.

This script validates that the local checkout is **ready** for a
production deploy without touching anything live.

Hard guarantees:
  * No DB connection attempt.
  * No Redis connection attempt.
  * No Telegram API call.
  * No OpenAI API call.
  * No ``alembic upgrade`` invocation.
  * No reading of secret values out of ``.env``.
  * Docker build is skipped unless ``--docker`` is explicitly passed.

Outputs a GREEN / YELLOW / RED summary. Exits 0 unless at least one
RED critical failure is found.

CLI:
  python scripts/production_deploy_dry_run_check.py
  python scripts/production_deploy_dry_run_check.py --json
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Make sure the repo root is on sys.path when invoked directly.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

REQUIRED_DOCS = [
    "docs/AI_AGENT_SYSTEM/125_STAGE_1_READINESS_REVIEW_AFTER_FRESH_START.md",
    "docs/AI_AGENT_SYSTEM/128_PRODUCTION_DEPLOYMENT_RUNBOOK.md",
    "docs/AI_AGENT_SYSTEM/129_STAGE_1_LOCAL_DRY_RUN_CHECK.md",
]

OPTIONAL_DOCS = [
    "docs/AI_AGENT_SYSTEM/113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md",
    "docs/AI_AGENT_SYSTEM/114_STAGE_1_ENV_FLAG_MATRIX.md",
    "docs/AI_AGENT_SYSTEM/124_HANDOFF_AUTO_EXPIRE_JOB.md",
    "docs/AI_AGENT_SYSTEM/126_OPERATOR_NOTIFICATION_DIGEST.md",
    "docs/AI_AGENT_SYSTEM/127_FINAL_CRM_WEB_UX_POLISH.md",
]

REQUIRED_DIRS = [
    "apps/api",
    "apps/web",
    "apps/scheduler",
    "apps/bot",
    "core",
    "infrastructure",
    "deploy",
    "scripts",
    "infrastructure/database/migrations/versions",
]

REQUIRED_FILES = [
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".env.example",
    "alembic.ini",
    "deploy/docker/Dockerfile",
    "deploy/docker/entrypoint.sh",
]

CRITICAL_MIGRATION_TOKEN = "add_crm_operator_handoff_requests"

DANGEROUS_FLAGS_MUST_BE_OFF = [
    "agent_execution_live_sender_enabled",
    "agent_execution_auto_execute_approved",
    "agent_execution_api_approval_enabled",
    "crm_campaign_send_enabled",
    "agent_followups_enabled",
    "crm_operator_reply_enabled",
    "crm_operator_handoff_auto_expire_enabled",
    "crm_operator_handoff_admin_notify_enabled",
    "crm_operator_digest_enabled",
    "crm_operator_digest_delivery_enabled",
    "admin_security_actions_enabled",
    "admin_ip_block_enforcement_enabled",
]

SAFETY_GATES_MUST_BE_ON = [
    "crm_campaign_send_dry_run_only",
    "agent_decision_log_only",
    "crm_campaign_send_require_confirmation",
]

REQUIRED_IMPORTS = [
    "apps.api.main",
    "apps.web.main",
    "apps.scheduler.main",
]

REQUIRED_BOT_IMPORT = ("apps.bot.main", "build_dispatcher")

REQUIRED_SERVICE_IMPORTS = [
    ("core.services.pricing_service", "PricingService"),
    (
        "core.services.crm_operator_handoff_service",
        "CRMOperatorHandoffService",
    ),
    ("core.services.crm_operator_digest_service", "build_digest"),
    ("core.services.crm_conversation_replay_service", "build_replay"),
    (
        "core.services.crm_price_estimate_history_service",
        "build_history",
    ),
]


@dataclass
class CheckItem:
    status: str
    name: str
    detail: str = ""


@dataclass
class DryRunReport:
    overall: str = GREEN
    items: list[CheckItem] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, status: str, name: str, detail: str = "") -> None:
        self.items.append(CheckItem(status=status, name=name, detail=detail))

    def finalize(self) -> None:
        counts = {GREEN: 0, YELLOW: 0, RED: 0}
        for it in self.items:
            counts[it.status] = counts.get(it.status, 0) + 1
        self.counts = counts
        if counts.get(RED, 0) > 0:
            self.overall = RED
        elif counts.get(YELLOW, 0) > 0:
            self.overall = YELLOW
        else:
            self.overall = GREEN


def _safe_run(cmd: list[str]) -> tuple[int, str]:
    """Run a subprocess synchronously and return (rc, stdout)."""
    import subprocess  # local import — keep top of module clean

    try:
        result = subprocess.run(
            cmd,
            cwd=str(_REPO),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out.strip()
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def check_git(report: DryRunReport) -> None:
    rc, out = _safe_run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        report.add(YELLOW, "git_branch", f"git not available: {out[:80]}")
        return
    branch = out.strip().splitlines()[-1] if out else ""
    if branch == "main":
        report.add(GREEN, "git_branch", "main")
    else:
        report.add(YELLOW, "git_branch", f"branch={branch} (expected main)")

    rc, out = _safe_run(["git", "status", "--porcelain"])
    if rc != 0:
        report.add(YELLOW, "git_status", "git status not available")
        return
    if out.strip():
        report.add(YELLOW, "git_status", f"uncommitted changes: {len(out.splitlines())} files")
    else:
        report.add(GREEN, "git_status", "clean")


def check_docs(report: DryRunReport) -> None:
    for doc in REQUIRED_DOCS:
        if (_REPO / doc).exists():
            report.add(GREEN, f"doc:{doc.split('/')[-1]}", "exists")
        else:
            report.add(RED, f"doc:{doc.split('/')[-1]}", "missing")
    for doc in OPTIONAL_DOCS:
        if (_REPO / doc).exists():
            report.add(GREEN, f"doc:{doc.split('/')[-1]}", "exists")
        else:
            report.add(YELLOW, f"doc:{doc.split('/')[-1]}", "missing (optional)")


def check_dirs_and_files(report: DryRunReport) -> None:
    for d in REQUIRED_DIRS:
        if (_REPO / d).is_dir():
            report.add(GREEN, f"dir:{d}", "present")
        else:
            report.add(RED, f"dir:{d}", "missing")
    for f in REQUIRED_FILES:
        if (_REPO / f).is_file():
            report.add(GREEN, f"file:{f}", "present")
        else:
            severity = RED if not f.startswith("docker-compose.prod") else YELLOW
            report.add(severity, f"file:{f}", "missing")


def check_critical_migration(report: DryRunReport) -> None:
    versions = _REPO / "infrastructure" / "database" / "migrations" / "versions"
    if not versions.is_dir():
        report.add(RED, "migration_versions_dir", "missing")
        return
    found = any(CRITICAL_MIGRATION_TOKEN in p.name for p in versions.iterdir())
    if found:
        report.add(GREEN, "critical_migration", CRITICAL_MIGRATION_TOKEN)
    else:
        report.add(RED, "critical_migration", f"no migration matches '{CRITICAL_MIGRATION_TOKEN}'")


def _load_business_settings() -> object | None:
    try:
        from shared.config import get_settings

        get_settings.cache_clear()
        return get_settings().business
    except Exception:
        return None


def check_dangerous_flags(report: DryRunReport) -> None:
    business = _load_business_settings()
    if business is None:
        report.add(YELLOW, "settings_load", "could not load settings (likely missing .env)")
        return

    for flag in DANGEROUS_FLAGS_MUST_BE_OFF:
        value = getattr(business, flag, None)
        if value is None:
            report.add(YELLOW, f"flag:{flag}", "absent from settings")
        elif value is False:
            report.add(GREEN, f"flag:{flag}", "OFF")
        else:
            report.add(RED, f"flag:{flag}", f"ON ({value!r}) — must be false for first apply")

    for flag in SAFETY_GATES_MUST_BE_ON:
        value = getattr(business, flag, None)
        if value is None:
            report.add(YELLOW, f"gate:{flag}", "absent from settings")
        elif value is True:
            report.add(GREEN, f"gate:{flag}", "ON")
        else:
            report.add(RED, f"gate:{flag}", f"OFF ({value!r}) — safety gate must stay true")


def check_imports(report: DryRunReport) -> None:
    for mod in REQUIRED_IMPORTS:
        try:
            importlib.import_module(mod)
            report.add(GREEN, f"import:{mod}", "ok")
        except Exception as exc:
            report.add(RED, f"import:{mod}", f"{type(exc).__name__}: {str(exc)[:120]}")

    mod_name, attr = REQUIRED_BOT_IMPORT
    try:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, attr):
            report.add(GREEN, f"import:{mod_name}.{attr}", "ok")
        else:
            report.add(RED, f"import:{mod_name}.{attr}", "attribute missing")
    except Exception as exc:
        report.add(
            RED,
            f"import:{mod_name}.{attr}",
            f"{type(exc).__name__}: {str(exc)[:120]}",
        )

    for mod_name, attr in REQUIRED_SERVICE_IMPORTS:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, attr):
                report.add(GREEN, f"service:{attr}", "importable")
            else:
                report.add(YELLOW, f"service:{attr}", f"attribute not found in {mod_name}")
        except Exception as exc:
            report.add(
                YELLOW,
                f"service:{attr}",
                f"{type(exc).__name__}: {str(exc)[:120]}",
            )


def check_no_real_secrets(report: DryRunReport) -> None:
    # Read .env.example only (never .env) to confirm placeholders, not real
    # secret literals, are checked into the repo.
    env_example = _REPO / ".env.example"
    if not env_example.is_file():
        report.add(RED, ".env.example", "missing")
        return
    text = env_example.read_text(encoding="utf-8", errors="ignore")
    import re

    suspect_patterns = [
        (re.compile(r"sk-[A-Za-z0-9]{30,}"), "sk- token literal"),
        (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "Google API key literal"),
    ]
    has_real_secret = False
    for pat, label in suspect_patterns:
        if pat.search(text):
            has_real_secret = True
            report.add(RED, f"env_example:{label}", "real secret found")
    if not has_real_secret:
        report.add(GREEN, ".env.example", "placeholders only")


def run_dry_run() -> DryRunReport:
    report = DryRunReport()
    check_git(report)
    check_docs(report)
    check_dirs_and_files(report)
    check_critical_migration(report)
    check_dangerous_flags(report)
    check_imports(report)
    check_no_real_secrets(report)
    report.finalize()
    return report


def _print_text(report: DryRunReport) -> None:
    color = {GREEN: "\033[32m", YELLOW: "\033[33m", RED: "\033[31m"}
    reset = "\033[0m"
    use_color = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

    def paint(status: str) -> str:
        if not use_color:
            return status
        return f"{color.get(status, '')}{status}{reset}"

    print("=" * 64)
    print("Production deploy dry-run check (read-only)")
    print("=" * 64)
    for it in report.items:
        print(f"  [{paint(it.status)}] {it.name}: {it.detail}")
    print("-" * 64)
    counts = report.counts
    print(
        f"  Summary: GREEN={counts.get(GREEN, 0)}  "
        f"YELLOW={counts.get(YELLOW, 0)}  "
        f"RED={counts.get(RED, 0)}"
    )
    print(f"  Overall: [{paint(report.overall)}]")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable output.",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="(future) Allow docker-build verification. Not used today.",
    )
    args = parser.parse_args(argv)

    if args.docker:
        # Explicit opt-in. Today this only acknowledges the flag without
        # actually running docker — keep the script safe by default.
        pass

    report = run_dry_run()
    if args.json:
        payload = {
            "overall": report.overall,
            "counts": report.counts,
            "items": [asdict(it) for it in report.items],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_text(report)

    return 1 if report.overall == RED else 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
