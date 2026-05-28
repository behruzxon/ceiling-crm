"""Step 13 — Production deploy dry-run script tests.

Verifies the script imports cleanly, never calls the network, runs to
completion, and returns the expected schema/severity for the current
checkout.
"""

from __future__ import annotations

import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

SCRIPT = Path("scripts/production_deploy_dry_run_check.py")


def _src() -> str:
    return SCRIPT.read_text(encoding="utf-8")


# ----------------------------- existence ------------------------------------


class TestScriptExists:
    def test_file_exists(self) -> None:
        assert SCRIPT.exists()

    def test_is_python_module(self) -> None:
        assert _src().startswith("#!/usr/bin/env python3") or "def main" in _src()


def _load_script(mod_name: str = "production_deploy_dry_run_check"):
    """Load the script as a module, registering it in sys.modules so the
    @dataclass decorator can resolve the module dict on Python 3.13+."""
    import importlib.util
    import sys as _sys

    if mod_name in _sys.modules:
        return _sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, str(SCRIPT.resolve()))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestImportsCleanly:
    def test_module_imports(self) -> None:
        mod = _load_script()
        assert hasattr(mod, "main")
        assert hasattr(mod, "run_dry_run")
        assert hasattr(mod, "GREEN")
        assert hasattr(mod, "YELLOW")
        assert hasattr(mod, "RED")


# ------------------------- runs end-to-end ----------------------------------


@pytest.fixture(scope="module")
def report():
    mod = _load_script()
    return mod.run_dry_run()


class TestRunDryRun:
    def test_returns_report_object(self, report) -> None:
        assert hasattr(report, "overall")
        assert hasattr(report, "items")
        assert hasattr(report, "counts")

    def test_overall_in_valid_set(self, report) -> None:
        assert report.overall in {"GREEN", "YELLOW", "RED"}

    def test_items_non_empty(self, report) -> None:
        assert len(report.items) > 0

    def test_counts_keys(self, report) -> None:
        for key in ("GREEN", "YELLOW", "RED"):
            assert key in report.counts

    def test_no_red_critical(self, report) -> None:
        # On current main the dry-run should not produce critical RED.
        assert report.counts.get("RED", 0) == 0


# ------------------------ doc presence detection ----------------------------


class TestDocsCheck:
    def test_doc_125_detected(self, report) -> None:
        names = [it.name for it in report.items]
        assert any("125_STAGE_1_READINESS" in n for n in names)

    def test_doc_128_detected(self, report) -> None:
        names = [it.name for it in report.items]
        assert any("128_PRODUCTION_DEPLOYMENT_RUNBOOK" in n for n in names)

    def test_doc_129_detected(self, report) -> None:
        names = [it.name for it in report.items]
        assert any("129_STAGE_1_LOCAL_DRY_RUN_CHECK" in n for n in names)


# ------------------------ dangerous flags audit -----------------------------


class TestFlagAudit:
    def test_lists_live_sender_flag(self) -> None:
        assert "agent_execution_live_sender_enabled" in _src()

    def test_lists_campaign_send_flag(self) -> None:
        assert "crm_campaign_send_enabled" in _src()

    def test_lists_followups_flag(self) -> None:
        assert "agent_followups_enabled" in _src()

    def test_lists_operator_reply_flag(self) -> None:
        assert "crm_operator_reply_enabled" in _src()

    def test_lists_handoff_expire_flag(self) -> None:
        assert "crm_operator_handoff_auto_expire_enabled" in _src()

    def test_lists_digest_flag(self) -> None:
        assert "crm_operator_digest_enabled" in _src()

    def test_lists_security_actions_flag(self) -> None:
        assert "admin_security_actions_enabled" in _src()

    def test_lists_ip_enforcement_flag(self) -> None:
        assert "admin_ip_block_enforcement_enabled" in _src()

    def test_lists_auto_execute_flag(self) -> None:
        assert "agent_execution_auto_execute_approved" in _src()

    def test_lists_safety_gates(self) -> None:
        assert "crm_campaign_send_dry_run_only" in _src()
        assert "agent_decision_log_only" in _src()


# ----------------------- required imports list ------------------------------


class TestRequiredImports:
    def test_api_main_listed(self) -> None:
        assert "apps.api.main" in _src()

    def test_web_main_listed(self) -> None:
        assert "apps.web.main" in _src()

    def test_scheduler_main_listed(self) -> None:
        assert "apps.scheduler.main" in _src()

    def test_bot_dispatcher_listed(self) -> None:
        assert "apps.bot.main" in _src() and "build_dispatcher" in _src()

    def test_handoff_service_listed(self) -> None:
        assert "CRMOperatorHandoffService" in _src()

    def test_digest_service_listed(self) -> None:
        assert "build_digest" in _src()

    def test_pricing_service_listed(self) -> None:
        assert "PricingService" in _src()


# ------------------------ no-network guarantees -----------------------------


class TestNoSideEffects:
    def test_no_telegram_call(self) -> None:
        src = _src()
        # No aiogram import, no Bot(...) construction
        assert "import aiogram" not in src
        assert "from aiogram" not in src
        assert "Bot(" not in src

    def test_no_openai_call(self) -> None:
        src = _src()
        assert "import openai" not in src
        assert "from openai" not in src

    def test_no_alembic_upgrade(self) -> None:
        src = _src()
        # Docstrings may mention "alembic upgrade" as a guarantee; only forbid
        # actual subprocess/CLI invocations.
        assert '"alembic"' not in src
        assert "'alembic'" not in src
        assert 'subprocess.run(["alembic' not in src
        assert "alembic.command" not in src
        assert "import alembic" not in src

    def test_no_db_connect(self) -> None:
        src = _src()
        assert "connect_database" not in src
        assert "create_engine" not in src

    def test_no_redis_connect(self) -> None:
        src = _src()
        assert "connect_redis" not in src
        assert "Redis(" not in src

    def test_docker_default_off(self) -> None:
        src = _src()
        # The CLI flag exists but docker is not built by default
        assert "--docker" in src
        assert "docker build" not in src.lower() or "actually running docker" in src.lower()

    def test_no_real_env_read(self) -> None:
        src = _src()
        # Reads .env.example only, never .env
        assert ".env.example" in src
        # No direct ".env" read
        assert 'open(".env")' not in src
        assert "open('.env')" not in src


# ---------------------------- JSON CLI mode ---------------------------------


class TestJsonOutput:
    def test_json_output_valid(self) -> None:
        mod = _load_script()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.main(["--json"])
        assert rc in (0, 1)
        payload = json.loads(buf.getvalue())
        assert "overall" in payload
        assert "counts" in payload
        assert "items" in payload

    def test_json_path_returns_zero_when_no_red(self) -> None:
        mod = _load_script()
        report = mod.run_dry_run()
        if report.counts.get("RED", 0) == 0:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = mod.main(["--json"])
            assert rc == 0


# --------------------------- severity surface -------------------------------


class TestSeverityStrings:
    def test_green_token_in_module(self) -> None:
        assert '"GREEN"' in _src() or "'GREEN'" in _src() or "GREEN =" in _src()

    def test_yellow_token_in_module(self) -> None:
        assert '"YELLOW"' in _src() or "'YELLOW'" in _src() or "YELLOW =" in _src()

    def test_red_token_in_module(self) -> None:
        assert '"RED"' in _src() or "'RED'" in _src() or "RED =" in _src()


# ----------------------- secret-leak guard in output ------------------------


class TestNoSecretLeak:
    def test_output_has_no_bot_token(self, report) -> None:
        rendered = json.dumps(
            [{"name": it.name, "detail": it.detail, "status": it.status} for it in report.items]
        )
        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", rendered)

    def test_output_has_no_sk_token(self, report) -> None:
        rendered = json.dumps(
            [{"name": it.name, "detail": it.detail, "status": it.status} for it in report.items]
        )
        assert "sk-" not in rendered

    def test_output_has_no_bearer(self, report) -> None:
        rendered = json.dumps(
            [{"name": it.name, "detail": it.detail, "status": it.status} for it in report.items]
        )
        assert "Bearer " not in rendered

    def test_output_has_no_postgres_url(self, report) -> None:
        rendered = json.dumps(
            [{"name": it.name, "detail": it.detail, "status": it.status} for it in report.items]
        )
        assert "postgresql://" not in rendered
        assert "postgresql+asyncpg://" not in rendered


# ---------------------- critical migration detection ------------------------


class TestCriticalMigration:
    def test_critical_migration_listed(self) -> None:
        assert "add_crm_operator_handoff_requests" in _src()

    def test_critical_migration_detected_on_current_main(self, report) -> None:
        for it in report.items:
            if it.name == "critical_migration":
                assert it.status == "GREEN"
                return
        raise AssertionError("critical_migration check not present in report")


_ = sys  # silence unused import on some toolchains
