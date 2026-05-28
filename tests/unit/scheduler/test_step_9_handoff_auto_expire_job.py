"""Step 9 — Handoff auto-expire scheduler job unit tests.

Verifies registration, no-op behavior when disabled, service dispatch when
enabled, error containment, and absence of Telegram/OpenAI calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestImports:
    def test_module_imports(self) -> None:
        import apps.scheduler.jobs.crm_handoff_expire_jobs as mod

        assert mod is not None

    def test_register_function_callable(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
        )

        assert callable(register_handoff_expire_jobs)

    def test_run_function_callable(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            run_handoff_expire_job,
        )

        assert callable(run_handoff_expire_job)

    def test_job_id_constant(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import JOB_ID

        assert JOB_ID == "crm_handoff_auto_expire"

    def test_default_interval_constant(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            DEFAULT_INTERVAL_MINUTES,
        )

        assert DEFAULT_INTERVAL_MINUTES == 15


class TestRegistration:
    def test_register_adds_job(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
        )

        scheduler = MagicMock()
        register_handoff_expire_jobs(scheduler)
        scheduler.add_job.assert_called_once()

    def test_register_uses_correct_job_id(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
        )

        scheduler = MagicMock()
        register_handoff_expire_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["id"] == "crm_handoff_auto_expire"

    def test_register_uses_interval_trigger(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
        )

        scheduler = MagicMock()
        register_handoff_expire_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["trigger"] == "interval"

    def test_register_uses_15_minute_interval(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
        )

        scheduler = MagicMock()
        register_handoff_expire_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["minutes"] == 15

    def test_register_replace_existing_true(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
        )

        scheduler = MagicMock()
        register_handoff_expire_jobs(scheduler)
        kwargs = scheduler.add_job.call_args[1]
        assert kwargs["replace_existing"] is True

    def test_register_passes_callable(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            register_handoff_expire_jobs,
            run_handoff_expire_job,
        )

        scheduler = MagicMock()
        register_handoff_expire_jobs(scheduler)
        args = scheduler.add_job.call_args[0]
        assert args[0] is run_handoff_expire_job

    def test_registered_in_scheduler_main(self) -> None:
        from apps.scheduler import main as scheduler_main

        src_path = scheduler_main.__file__ or ""
        assert src_path
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        assert "register_handoff_expire_jobs" in src


def _make_settings(enabled: bool, hours: int = 24, batch: int = 100) -> SimpleNamespace:
    business = SimpleNamespace(
        crm_operator_handoff_auto_expire_enabled=enabled,
        crm_operator_handoff_expire_hours=hours,
        crm_operator_handoff_expire_batch_limit=batch,
    )
    return SimpleNamespace(business=business)


class TestRunBehavior:
    @pytest.mark.asyncio
    async def test_disabled_flag_no_op(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        fake_service = AsyncMock()
        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=False),
            ),
            patch.object(
                mod,
                "__name__",
                mod.__name__,
            ),
            patch(
                "core.services.crm_operator_handoff_service.CRMOperatorHandoffService",
                fake_service,
            ),
        ):
            await mod.run_handoff_expire_job()

        fake_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_enabled_flag_calls_service(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        fake_result = SimpleNamespace(
            scanned=2, expired_count=1, skipped_count=1, expired_ids=(7,), errors=()
        )
        service_instance = MagicMock()
        service_instance.expire_stale_handoffs = AsyncMock(return_value=fake_result)
        service_class = MagicMock(return_value=service_instance)

        class _FakeSession:
            async def __aenter__(self) -> object:
                return object()

            async def __aexit__(self, *args: object) -> None:
                return None

        factory = MagicMock(return_value=_FakeSession())

        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=True, hours=24, batch=50),
            ),
            patch(
                "core.services.crm_operator_handoff_service.CRMOperatorHandoffService",
                service_class,
            ),
            patch(
                "infrastructure.database.session.get_session_factory",
                return_value=factory,
            ),
        ):
            await mod.run_handoff_expire_job()

        service_instance.expire_stale_handoffs.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enabled_passes_expire_hours_from_config(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        service_instance = MagicMock()
        service_instance.expire_stale_handoffs = AsyncMock(
            return_value=SimpleNamespace(
                scanned=0,
                expired_count=0,
                skipped_count=0,
                expired_ids=(),
                errors=(),
            )
        )
        service_class = MagicMock(return_value=service_instance)

        class _FakeSession:
            async def __aenter__(self) -> object:
                return object()

            async def __aexit__(self, *args: object) -> None:
                return None

        factory = MagicMock(return_value=_FakeSession())

        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=True, hours=48, batch=33),
            ),
            patch(
                "core.services.crm_operator_handoff_service.CRMOperatorHandoffService",
                service_class,
            ),
            patch(
                "infrastructure.database.session.get_session_factory",
                return_value=factory,
            ),
        ):
            await mod.run_handoff_expire_job()

        kwargs = service_instance.expire_stale_handoffs.await_args.kwargs
        assert kwargs["expire_hours"] == 48
        assert kwargs["limit"] == 33

    @pytest.mark.asyncio
    async def test_enabled_passes_batch_limit_from_config(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        service_instance = MagicMock()
        service_instance.expire_stale_handoffs = AsyncMock(
            return_value=SimpleNamespace(
                scanned=0,
                expired_count=0,
                skipped_count=0,
                expired_ids=(),
                errors=(),
            )
        )
        service_class = MagicMock(return_value=service_instance)

        class _FakeSession:
            async def __aenter__(self) -> object:
                return object()

            async def __aexit__(self, *args: object) -> None:
                return None

        factory = MagicMock(return_value=_FakeSession())

        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=True, hours=12, batch=77),
            ),
            patch(
                "core.services.crm_operator_handoff_service.CRMOperatorHandoffService",
                service_class,
            ),
            patch(
                "infrastructure.database.session.get_session_factory",
                return_value=factory,
            ),
        ):
            await mod.run_handoff_expire_job()

        assert service_instance.expire_stale_handoffs.await_args.kwargs["limit"] == 77

    @pytest.mark.asyncio
    async def test_config_error_caught(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        with patch(
            "shared.config.get_settings",
            side_effect=RuntimeError("config exploded"),
        ):
            await mod.run_handoff_expire_job()  # should not raise

    @pytest.mark.asyncio
    async def test_session_factory_error_caught(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=True),
            ),
            patch(
                "infrastructure.database.session.get_session_factory",
                side_effect=RuntimeError("db down"),
            ),
        ):
            await mod.run_handoff_expire_job()  # should not raise

    @pytest.mark.asyncio
    async def test_service_error_caught(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        service_instance = MagicMock()
        service_instance.expire_stale_handoffs = AsyncMock(
            side_effect=RuntimeError("service exploded")
        )
        service_class = MagicMock(return_value=service_instance)

        class _FakeSession:
            async def __aenter__(self) -> object:
                return object()

            async def __aexit__(self, *args: object) -> None:
                return None

        factory = MagicMock(return_value=_FakeSession())

        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=True),
            ),
            patch(
                "core.services.crm_operator_handoff_service.CRMOperatorHandoffService",
                service_class,
            ),
            patch(
                "infrastructure.database.session.get_session_factory",
                return_value=factory,
            ),
        ):
            await mod.run_handoff_expire_job()  # should not raise

    @pytest.mark.asyncio
    async def test_disabled_does_not_open_session(self) -> None:
        from apps.scheduler.jobs import crm_handoff_expire_jobs as mod

        factory = MagicMock()
        with (
            patch(
                "shared.config.get_settings",
                return_value=_make_settings(enabled=False),
            ),
            patch(
                "infrastructure.database.session.get_session_factory",
                return_value=factory,
            ),
        ):
            await mod.run_handoff_expire_job()

        factory.assert_not_called()


class TestSourceSafety:
    def test_no_telegram_imports_in_module(self) -> None:
        import apps.scheduler.jobs.crm_handoff_expire_jobs as mod

        src_path = mod.__file__ or ""
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        assert "aiogram" not in src
        assert "telegram" not in src.lower()

    def test_no_openai_imports_in_module(self) -> None:
        import apps.scheduler.jobs.crm_handoff_expire_jobs as mod

        src_path = mod.__file__ or ""
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        assert "openai" not in src.lower()

    def test_no_send_message_in_module(self) -> None:
        import apps.scheduler.jobs.crm_handoff_expire_jobs as mod

        src_path = mod.__file__ or ""
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        assert "send_message" not in src
        assert "safe_send" not in src

    def test_no_delete_in_module(self) -> None:
        import apps.scheduler.jobs.crm_handoff_expire_jobs as mod

        src_path = mod.__file__ or ""
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        assert ".delete(" not in src
        assert "DELETE FROM" not in src.upper().replace("DELETED", "")


class TestSettingsContract:
    def test_settings_has_auto_expire_enabled_flag(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert hasattr(s.business, "crm_operator_handoff_auto_expire_enabled")

    def test_default_auto_expire_is_false(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert s.business.crm_operator_handoff_auto_expire_enabled is False

    def test_settings_has_expire_hours(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert hasattr(s.business, "crm_operator_handoff_expire_hours")
        assert s.business.crm_operator_handoff_expire_hours == 24

    def test_settings_has_batch_limit(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert hasattr(s.business, "crm_operator_handoff_expire_batch_limit")
        assert s.business.crm_operator_handoff_expire_batch_limit == 100


class TestModuleStructure:
    def test_register_in_scheduler_main_imports(self) -> None:
        from apps.scheduler import main

        assert hasattr(main, "register_handoff_expire_jobs")

    def test_scheduler_main_calls_register_handoff(self) -> None:
        from apps.scheduler import main as scheduler_main

        src_path = scheduler_main.__file__ or ""
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        assert "register_handoff_expire_jobs(scheduler)" in src

    def test_run_function_is_async(self) -> None:
        import inspect

        from apps.scheduler.jobs.crm_handoff_expire_jobs import (
            run_handoff_expire_job,
        )

        assert inspect.iscoroutinefunction(run_handoff_expire_job)
