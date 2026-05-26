"""Tests for Step AK — Agent execution scheduler job registration."""
from __future__ import annotations

from unittest.mock import MagicMock


class TestJobRegistration:
    def test_scheduler_imports(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None

    def test_expire_job_register_function(self):
        from apps.scheduler.jobs.agent_execution_jobs import (
            register_agent_execution_jobs,
        )
        assert callable(register_agent_execution_jobs)

    def test_sender_job_register_function(self):
        from apps.scheduler.jobs.approved_execution_sender_jobs import (
            register_approved_execution_sender_jobs,
        )
        assert callable(register_approved_execution_sender_jobs)

    def test_expire_job_registers(self):
        from apps.scheduler.jobs.agent_execution_jobs import (
            register_agent_execution_jobs,
        )
        scheduler = MagicMock()
        register_agent_execution_jobs(scheduler)
        scheduler.add_job.assert_called_once()
        call_kwargs = scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "agent_expire_pending_executions"

    def test_sender_job_registers(self):
        from apps.scheduler.jobs.approved_execution_sender_jobs import (
            register_approved_execution_sender_jobs,
        )
        scheduler = MagicMock()
        register_approved_execution_sender_jobs(scheduler)
        scheduler.add_job.assert_called_once()
        call_kwargs = scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "agent_process_approved_executions"

    def test_expire_job_interval_5min(self):
        from apps.scheduler.jobs.agent_execution_jobs import (
            register_agent_execution_jobs,
        )
        scheduler = MagicMock()
        register_agent_execution_jobs(scheduler)
        call_args = scheduler.add_job.call_args
        assert call_args[1].get("minutes") == 5

    def test_sender_job_interval_1min(self):
        from apps.scheduler.jobs.approved_execution_sender_jobs import (
            register_approved_execution_sender_jobs,
        )
        scheduler = MagicMock()
        register_approved_execution_sender_jobs(scheduler)
        call_args = scheduler.add_job.call_args
        assert call_args[1].get("minutes") == 1


class TestFeatureFlagSafety:
    def test_queue_disabled_default(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_execution_queue_enabled"
        ].default is False

    def test_live_sender_disabled_default(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_execution_live_sender_enabled"
        ].default is False

    def test_auto_execute_disabled_default(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_execution_auto_execute_approved"
        ].default is False

    def test_expire_job_callable(self):
        from apps.scheduler.jobs.agent_execution_jobs import (
            expire_pending_executions,
        )
        assert callable(expire_pending_executions)

    def test_sender_job_callable(self):
        from apps.scheduler.jobs.approved_execution_sender_jobs import (
            process_approved_executions,
        )
        assert callable(process_approved_executions)


class TestNonRegression:
    def test_bot_main_importable(self):
        import apps.bot.main
        assert apps.bot.main is not None

    def test_signal_still_works(self):
        from core.services.lead_signal_service import LeadSignalService
        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"
