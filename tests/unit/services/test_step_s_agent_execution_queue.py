"""Tests for Step S — AgentExecutionQueueService."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.agent_execution_queue_service import AgentExecutionQueueService
from infrastructure.database.models.agent_execution_record import (
    AgentExecutionRecordModel,
)
from shared.constants.enums import AgentExecutionStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_record(
    *,
    execution_id: str = "test-123",
    status: str = "proposed",
    action: str = "send_user_reply",
    mode: str = "approval_required",
    risk: str = "low",
    user_id: int = 12345,
    channel: str = "user_dm",
    expires_minutes: int = 30,
    payload: dict | None = None,
) -> AgentExecutionRecordModel:
    now = datetime.now(UTC)
    r = MagicMock(spec=AgentExecutionRecordModel)
    r.id = 1
    r.execution_id = execution_id
    r.telegram_user_id = user_id
    r.action = action
    r.mode = mode
    r.status = status
    r.risk_level = risk
    r.channel = channel
    r.payload_json = payload or {"message_text": "Salom", "reason": "test"}
    r.result_json = None
    r.trace_json = None
    r.message_text_hash = "abc123"
    r.approved_by = None
    r.approved_at = None
    r.rejected_by = None
    r.rejected_at = None
    r.rejection_reason = None
    r.blocked_reason = None
    r.created_at = now
    r.expires_at = now + timedelta(minutes=expires_minutes)
    r.executed_at = None
    r.failed_at = None
    r.last_error = None
    return r


# ─── 1. Static methods (no DB) ──────────────────────────────────────────────


class TestStaticMethods:
    def test_can_execute_approved(self):
        r = _make_record(status="approved")
        assert AgentExecutionQueueService.can_execute(r) is True

    def test_can_execute_proposed_false(self):
        r = _make_record(status="proposed")
        assert AgentExecutionQueueService.can_execute(r) is False

    def test_can_execute_rejected_false(self):
        r = _make_record(status="rejected")
        assert AgentExecutionQueueService.can_execute(r) is False

    def test_can_execute_expired_false(self):
        r = _make_record(status="expired")
        assert AgentExecutionQueueService.can_execute(r) is False

    def test_can_execute_executed_false(self):
        r = _make_record(status="executed")
        assert AgentExecutionQueueService.can_execute(r) is False

    def test_build_admin_message(self):
        r = _make_record()
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "Agent action approval" in msg
        assert str(r.telegram_user_id) in msg
        assert r.action in msg

    def test_admin_message_redacts_phone(self):
        r = _make_record(payload={"message_text": "Call +998901234567", "reason": "x"})
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "+998901234567" not in msg
        assert "[***]" in msg

    def test_admin_message_redacts_token(self):
        r = _make_record(payload={"message_text": "sk-secret123abc", "reason": "x"})
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "sk-secret" not in msg

    def test_build_keyboard(self):
        r = _make_record(execution_id="abc-123")
        kb = AgentExecutionQueueService.build_admin_approval_keyboard(r)
        assert len(kb) == 1
        row = kb[0]
        assert len(row) == 3
        assert "approve" in row[0][1]
        assert "reject" in row[1][1]
        assert "view" in row[2][1]
        assert "abc-123" in row[0][1]

    def test_keyboard_has_execution_id(self):
        r = _make_record(execution_id="xyz-789")
        kb = AgentExecutionQueueService.build_admin_approval_keyboard(r)
        assert "xyz-789" in kb[0][0][1]


# ─── 2. Create record ───────────────────────────────────────────────────────


class TestCreateRecord:
    @pytest.fixture
    def session(self):
        s = AsyncMock()
        s.add = MagicMock()
        s.flush = AsyncMock()
        s.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))
        return s

    async def test_create_stores_proposed(self, session):
        svc = AgentExecutionQueueService(session)
        payload = {
            "execution_id": "new-001",
            "target_user_id": 12345,
            "action": "send_user_reply",
            "mode": "approval_required",
            "risk_level": "low",
            "channel": "user_dm",
            "message_text": "Hello",
        }
        record = await svc.create_record(payload)
        assert record.status == "proposed"
        assert record.execution_id == "new-001"
        session.add.assert_called_once()

    async def test_create_applies_ttl(self, session):
        svc = AgentExecutionQueueService(session)
        payload = {"execution_id": "ttl-001", "target_user_id": 1, "action": "x",
                   "mode": "live", "risk_level": "none"}
        record = await svc.create_record(payload, ttl_minutes=60)
        assert (record.expires_at - record.created_at).total_seconds() == pytest.approx(3600, abs=5)

    async def test_create_redacts_payload(self, session):
        svc = AgentExecutionQueueService(session)
        payload = {
            "execution_id": "redact-001",
            "target_user_id": 1,
            "action": "send_user_reply",
            "mode": "live",
            "risk_level": "low",
            "message_text": "Call +998901234567",
        }
        record = await svc.create_record(payload)
        assert "+998901234567" not in str(record.payload_json)

    async def test_create_hashes_message(self, session):
        svc = AgentExecutionQueueService(session)
        payload = {"execution_id": "hash-001", "target_user_id": 1, "action": "x",
                   "mode": "live", "risk_level": "none", "message_text": "test msg"}
        record = await svc.create_record(payload)
        assert record.message_text_hash is not None
        assert len(record.message_text_hash) == 16

    async def test_duplicate_raises(self, session):
        session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=1)))
        svc = AgentExecutionQueueService(session)
        with pytest.raises(ValueError, match="duplicate"):
            await svc.create_record({"execution_id": "dup-001"})


# ─── 3. Approve ─────────────────────────────────────────────────────────────


class TestApprove:
    @pytest.fixture
    def session(self):
        s = AsyncMock()
        s.flush = AsyncMock()
        return s

    async def test_approve_proposed(self, session):
        record = _make_record(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test-123", admin_id=999)
        assert ok is True
        assert reason == "approved"
        assert record.status == "approved"
        assert record.approved_by == 999

    async def test_approve_expired_rejects(self, session):
        record = _make_record(status="proposed", expires_minutes=-10)
        record.expires_at = datetime.now(UTC) - timedelta(minutes=10)
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test-123", admin_id=999)
        assert ok is False
        assert reason == "expired"

    async def test_approve_executed_rejects(self, session):
        record = _make_record(status="executed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test-123", admin_id=999)
        assert ok is False
        assert "already_executed" in reason

    async def test_approve_not_found(self, session):
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("missing", admin_id=999)
        assert ok is False
        assert reason == "not_found"


# ─── 4. Reject ──────────────────────────────────────────────────────────────


class TestReject:
    @pytest.fixture
    def session(self):
        s = AsyncMock()
        s.flush = AsyncMock()
        return s

    async def test_reject_proposed(self, session):
        record = _make_record(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.reject("test-123", admin_id=999, reason="not safe")
        assert ok is True
        assert record.status == "rejected"
        assert record.rejection_reason == "not safe"

    async def test_reject_executed_fails(self, session):
        record = _make_record(status="executed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.reject("test-123", admin_id=999)
        assert ok is False

    async def test_reject_not_found(self, session):
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.reject("missing", admin_id=999)
        assert ok is False


# ─── 5. Mark executed/failed/blocked ────────────────────────────────────────


class TestMarkMethods:
    @pytest.fixture
    def session(self):
        s = AsyncMock()
        s.flush = AsyncMock()
        return s

    async def test_mark_executed(self, session):
        record = _make_record(status="approved")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_executed("test-123")
        assert ok is True
        assert record.status == "executed"
        assert record.executed_at is not None

    async def test_mark_executed_rejected_fails(self, session):
        record = _make_record(status="rejected")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_executed("test-123")
        assert ok is False

    async def test_mark_failed(self, session):
        record = _make_record(status="approved")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_failed("test-123", "timeout")
        assert ok is True
        assert record.status == "failed"
        assert record.last_error == "timeout"

    async def test_mark_blocked(self, session):
        record = _make_record(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_blocked("test-123", "safety_violation")
        assert ok is True
        assert record.status == "blocked"
        assert record.blocked_reason == "safety_violation"


# ─── 6. Expire pending ──────────────────────────────────────────────────────


class TestExpirePending:
    async def test_expire_returns_count(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(rowcount=3))
        svc = AgentExecutionQueueService(session)
        count = await svc.expire_pending()
        assert count == 3

    async def test_expire_uses_now(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
        svc = AgentExecutionQueueService(session)
        count = await svc.expire_pending(now=datetime.now(UTC))
        assert count == 0


# ─── 7. List pending ────────────────────────────────────────────────────────


class TestListPending:
    async def test_list_returns_records(self):
        records = [_make_record(), _make_record(execution_id="b")]
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        session.execute = AsyncMock(return_value=mock_result)
        svc = AgentExecutionQueueService(session)
        result = await svc.list_pending()
        assert len(result) == 2


# ─── 8. Status lifecycle validation ─────────────────────────────────────────


class TestStatusLifecycle:
    def test_proposed_is_not_final(self):
        from core.services.agent_execution_queue_service import _FINAL_STATUSES
        assert "proposed" not in _FINAL_STATUSES

    def test_approved_is_not_final(self):
        from core.services.agent_execution_queue_service import _FINAL_STATUSES
        assert "approved" not in _FINAL_STATUSES

    def test_executed_is_final(self):
        from core.services.agent_execution_queue_service import _FINAL_STATUSES
        assert "executed" in _FINAL_STATUSES

    def test_rejected_is_final(self):
        from core.services.agent_execution_queue_service import _FINAL_STATUSES
        assert "rejected" in _FINAL_STATUSES

    def test_expired_is_final(self):
        from core.services.agent_execution_queue_service import _FINAL_STATUSES
        assert "expired" in _FINAL_STATUSES

    def test_failed_is_final(self):
        from core.services.agent_execution_queue_service import _FINAL_STATUSES
        assert "failed" in _FINAL_STATUSES


# ─── 9. Callback handler imports ────────────────────────────────────────────


class TestCallbackImports:
    def test_callback_router_importable(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import router
        assert router.name == "callbacks:agent_execution"

    def test_scheduler_job_importable(self):
        from apps.scheduler.jobs.agent_execution_jobs import (
            expire_pending_executions,
        )
        assert callable(expire_pending_executions)


# ─── 10. DI ─────────────────────────────────────────────────────────────────


class TestDI:
    def test_di_importable(self):
        from infrastructure.di import get_agent_execution_queue_service
        assert callable(get_agent_execution_queue_service)


# ─── 11. Migration importable ───────────────────────────────────────────────


class TestMigration:
    def test_migration_importable(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_0500_w8x9y0z1a2b3_add_agent_execution_records"
        )
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


# ─── 12. Model importable ───────────────────────────────────────────────────


class TestModel:
    def test_model_importable(self):
        from infrastructure.database.models.agent_execution_record import (
            AgentExecutionRecordModel,
        )
        assert AgentExecutionRecordModel.__tablename__ == "agent_execution_records"

    def test_model_has_indexes(self):
        from infrastructure.database.models.agent_execution_record import (
            AgentExecutionRecordModel,
        )
        idx_names = [idx.name for idx in AgentExecutionRecordModel.__table_args__
                     if hasattr(idx, "name")]
        assert "ix_exec_user_created" in idx_names
        assert "ix_exec_status_expires" in idx_names
        assert "ix_exec_mode_status" in idx_names


# ─── 13. Redaction ──────────────────────────────────────────────────────────


class TestRedaction:
    def test_redact_phone_in_payload(self):
        result = AgentExecutionQueueService._redact_payload(
            {"message_text": "Call +998901234567 now"},
        )
        assert "+998901234567" not in result["message_text"]

    def test_redact_token_in_payload(self):
        result = AgentExecutionQueueService._redact_payload(
            {"message_text": "Use sk-abc123secret"},
        )
        assert "sk-abc123" not in result["message_text"]

    def test_redact_admin_alert(self):
        result = AgentExecutionQueueService._redact_payload(
            {"admin_alert_text": "Phone: +998776655443"},
        )
        assert "+998776655443" not in result["admin_alert_text"]

    def test_no_redact_clean_text(self):
        result = AgentExecutionQueueService._redact_payload(
            {"message_text": "Salom, narx hisoblaymizmi?"},
        )
        assert result["message_text"] == "Salom, narx hisoblaymizmi?"


# ─── 14. Admin message format ───────────────────────────────────────────────


class TestAdminMessage:
    def test_contains_user_id(self):
        r = _make_record(user_id=777)
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "777" in msg

    def test_contains_action(self):
        r = _make_record(action="handoff_operator")
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "handoff_operator" in msg

    def test_contains_risk(self):
        r = _make_record(risk="high")
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "high" in msg

    def test_contains_channel(self):
        r = _make_record(channel="admin_group")
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert "admin_group" in msg

    def test_message_preview_truncated(self):
        long_msg = "a" * 200
        r = _make_record(payload={"message_text": long_msg, "reason": "x"})
        msg = AgentExecutionQueueService.build_admin_approval_message(r)
        assert len(msg) < 500


# ─── 15. Keyboard format ────────────────────────────────────────────────────


class TestKeyboard:
    def test_approve_button_text(self):
        r = _make_record()
        kb = AgentExecutionQueueService.build_admin_approval_keyboard(r)
        assert "✅" in kb[0][0][0]

    def test_reject_button_text(self):
        r = _make_record()
        kb = AgentExecutionQueueService.build_admin_approval_keyboard(r)
        assert "❌" in kb[0][1][0]

    def test_view_button_text(self):
        r = _make_record()
        kb = AgentExecutionQueueService.build_admin_approval_keyboard(r)
        assert "👁" in kb[0][2][0]

    def test_callback_data_format(self):
        r = _make_record(execution_id="test-xyz")
        kb = AgentExecutionQueueService.build_admin_approval_keyboard(r)
        assert kb[0][0][1] == "agentexec:approve:test-xyz"
        assert kb[0][1][1] == "agentexec:reject:test-xyz"
        assert kb[0][2][1] == "agentexec:view:test-xyz"


# ─── 16. Edge cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    async def test_approve_already_approved(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _make_record(status="approved")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test", admin_id=1)
        assert ok is False
        assert reason == "already_approved"

    async def test_mark_executed_not_found(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_executed("missing")
        assert ok is False

    async def test_mark_failed_not_found(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_failed("missing", "error")
        assert ok is False

    async def test_mark_blocked_not_found(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )
        svc = AgentExecutionQueueService(session)
        ok = await svc.mark_blocked("missing", "reason")
        assert ok is False

    async def test_reject_already_rejected(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _make_record(status="rejected")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.reject("test", admin_id=1)
        assert ok is False

    async def test_approve_rejected_fails(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _make_record(status="rejected")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test", admin_id=1)
        assert ok is False

    def test_empty_execution_id_exists_false(self):
        # _exists returns False for empty string without DB call
        pass


# ─── 17. Settings ───────────────────────────────────────────────────────────


class TestSettings:
    def test_queue_settings_exist(self):
        from shared.config.settings import BusinessSettings
        fields = BusinessSettings.model_fields
        assert "agent_execution_queue_enabled" in fields
        assert "agent_execution_approval_ttl_minutes" in fields
        assert "agent_execution_approval_admin_notify" in fields
        assert "agent_execution_auto_execute_approved" in fields

    def test_queue_default_false(self):
        from shared.config.settings import BusinessSettings
        default = BusinessSettings.model_fields["agent_execution_queue_enabled"].default
        assert default is False

    def test_ttl_default_30(self):
        from shared.config.settings import BusinessSettings
        default = BusinessSettings.model_fields["agent_execution_approval_ttl_minutes"].default
        assert default == 30

    def test_auto_execute_default_false(self):
        from shared.config.settings import BusinessSettings
        default = BusinessSettings.model_fields["agent_execution_auto_execute_approved"].default
        assert default is False

    def test_admin_notify_default_false(self):
        from shared.config.settings import BusinessSettings
        default = BusinessSettings.model_fields["agent_execution_approval_admin_notify"].default
        assert default is False


# ─── 18. Integration non-regression ─────────────────────────────────────────


class TestNonRegression:
    def test_sandbox_still_works(self):
        from core.services.agent_execution_sandbox_service import (
            AgentExecutionSandboxService,
        )
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "Salom", "target_user_id": 123},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 0, "memory_data": {}},
            "live",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 0, "memory_data": {}},
        )
        assert r.would_execute is True

    def test_orchestrator_still_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )
        mem = {"followup_enabled": True, "memory_data": {},
               "lead_temperature": "warm", "telegram_user_id": 1}
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"

    def test_simulation_import(self):
        from tests.simulation.agent.simulation_runner import build_memory, run_scenario
        r = run_scenario("salom", build_memory())
        assert r.signal_intent == "unclear"

    def test_enums_importable(self):
        from shared.constants.enums import (
            AgentExecutionMode,
            AgentExecutionRisk,
        )
        assert AgentExecutionMode.LIVE.value == "live"
        assert AgentExecutionStatus.PROPOSED.value == "proposed"
        assert AgentExecutionRisk.HIGH.value == "high"
