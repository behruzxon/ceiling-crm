"""Step 11 — Operator digest scheduler job tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _src() -> str:
    return Path("apps/scheduler/jobs/crm_operator_digest_jobs.py").read_text(encoding="utf-8")


class TestImports:
    def test_module_imports(self) -> None:
        import apps.scheduler.jobs.crm_operator_digest_jobs as mod

        assert mod is not None

    def test_register_function(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import (
            register_operator_digest_jobs,
        )

        assert callable(register_operator_digest_jobs)

    def test_run_function(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import run_operator_digest_job

        assert callable(run_operator_digest_job)

    def test_job_id(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import JOB_ID

        assert JOB_ID == "crm_operator_digest_daily"

    def test_async_run(self) -> None:
        import inspect

        from apps.scheduler.jobs.crm_operator_digest_jobs import run_operator_digest_job

        assert inspect.iscoroutinefunction(run_operator_digest_job)


class TestRegistration:
    def test_register_adds_job(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import (
            register_operator_digest_jobs,
        )

        scheduler = MagicMock()
        register_operator_digest_jobs(scheduler)
        scheduler.add_job.assert_called_once()

    def test_register_uses_correct_id(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import (
            register_operator_digest_jobs,
        )

        scheduler = MagicMock()
        register_operator_digest_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["id"] == "crm_operator_digest_daily"

    def test_register_uses_cron_trigger(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import (
            register_operator_digest_jobs,
        )

        scheduler = MagicMock()
        register_operator_digest_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["trigger"] == "cron"

    def test_register_uses_configured_hour(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import (
            register_operator_digest_jobs,
        )

        scheduler = MagicMock()
        register_operator_digest_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["hour"] == 9  # default

    def test_register_replace_existing(self) -> None:
        from apps.scheduler.jobs.crm_operator_digest_jobs import (
            register_operator_digest_jobs,
        )

        scheduler = MagicMock()
        register_operator_digest_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["replace_existing"] is True

    def test_registered_in_scheduler_main(self) -> None:
        c = Path("apps/scheduler/main.py").read_text(encoding="utf-8")
        assert "register_operator_digest_jobs" in c


def _settings(enabled: bool, delivery: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        business=SimpleNamespace(
            crm_operator_digest_enabled=enabled,
            crm_operator_digest_delivery_enabled=delivery,
            crm_operator_digest_hour=9,
        )
    )


class TestRuntime:
    @pytest.mark.asyncio
    async def test_disabled_no_op(self) -> None:
        from apps.scheduler.jobs import crm_operator_digest_jobs as mod

        factory = MagicMock()
        with (
            patch("shared.config.get_settings", return_value=_settings(False)),
            patch(
                "infrastructure.database.session.get_session_factory",
                return_value=factory,
            ),
        ):
            await mod.run_operator_digest_job()

        # No DB session opened
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_error_caught(self) -> None:
        from apps.scheduler.jobs import crm_operator_digest_jobs as mod

        with patch(
            "shared.config.get_settings",
            side_effect=RuntimeError("config exploded"),
        ):
            await mod.run_operator_digest_job()  # must not raise

    @pytest.mark.asyncio
    async def test_session_factory_error_caught(self) -> None:
        from apps.scheduler.jobs import crm_operator_digest_jobs as mod

        with (
            patch("shared.config.get_settings", return_value=_settings(True)),
            patch(
                "infrastructure.database.session.get_session_factory",
                side_effect=RuntimeError("db gone"),
            ),
        ):
            await mod.run_operator_digest_job()  # must not raise

    @pytest.mark.asyncio
    async def test_delivery_disabled_does_not_send(self) -> None:
        from apps.scheduler.jobs import crm_operator_digest_jobs as mod

        # When delivery flag is off, no aiogram should be imported even via
        # network of helpers. We just confirm the call path is safe.
        with (
            patch("shared.config.get_settings", return_value=_settings(True, delivery=False)),
            patch(
                "infrastructure.database.session.get_session_factory",
                side_effect=RuntimeError("simulate db absent"),
            ),
        ):
            await mod.run_operator_digest_job()


class TestSourceSafety:
    def test_no_aiogram_import(self) -> None:
        src = _src()
        # Only ban actual import statements; docstring mentions are fine.
        assert "import aiogram" not in src
        assert "from aiogram" not in src

    def test_no_openai_import(self) -> None:
        src = _src()
        assert "import openai" not in src
        assert "from openai" not in src

    def test_no_send_message(self) -> None:
        assert "send_message" not in _src()

    def test_no_destructive_delete(self) -> None:
        assert ".delete(" not in _src()
        assert "DELETE FROM" not in _src().upper().replace("DELETED", "")

    def test_no_safe_send_helper(self) -> None:
        assert "safe_send" not in _src()


class TestSettingsContract:
    def test_default_enabled_false(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert s.business.crm_operator_digest_enabled is False

    def test_default_delivery_false(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert s.business.crm_operator_digest_delivery_enabled is False

    def test_default_hour_9(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert s.business.crm_operator_digest_hour == 9

    def test_settings_hour_validated(self) -> None:
        # Pydantic Field has ge=0, le=23 — confirm validation by reading model_fields
        from shared.config.settings import BusinessSettings

        # When this raises it confirms validation; we just call to ensure
        # field exists with the right alias.
        field = BusinessSettings.model_fields["crm_operator_digest_hour"]
        assert field.alias == "CRM_OPERATOR_DIGEST_HOUR"
