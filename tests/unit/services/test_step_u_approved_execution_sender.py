"""Tests for Step U — ApprovedExecutionSenderService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from core.services.approved_execution_sender_service import (
    ApprovedExecutionSenderService,
)
from infrastructure.database.models.agent_execution_record import (
    AgentExecutionRecordModel,
)

svc = ApprovedExecutionSenderService


def _rec(
    *,
    status: str = "approved",
    action: str = "send_user_reply",
    mode: str = "live",
    risk: str = "low",
    user_id: int = 12345,
    channel: str = "user_dm",
    msg: str = "Salom",
    expires_minutes: int = 30,
    executed_at: datetime | None = None,
    failed_at: datetime | None = None,
    execution_id: str = "test-001",
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
    r.payload_json = {"message_text": msg, "admin_alert_text": msg}
    r.result_json = None
    r.message_text_hash = "abc"
    r.approved_by = 999
    r.approved_at = now
    r.rejected_by = None
    r.rejected_at = None
    r.blocked_reason = None
    r.created_at = now
    r.expires_at = now + timedelta(minutes=expires_minutes)
    r.executed_at = executed_at
    r.failed_at = failed_at
    r.last_error = None
    return r


def _bot(success: bool = True) -> AsyncMock:
    b = AsyncMock()
    if success:
        b.send_message = AsyncMock(return_value=MagicMock())
    else:
        b.send_message = AsyncMock(side_effect=Exception("send failed"))
    return b


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Status validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusValidation:
    def test_proposed_blocked(self):
        r = svc.validate_before_send(_rec(status="proposed"))
        assert r.blocked is True
        assert "proposed" in (r.blocked_reason or "")

    def test_rejected_blocked(self):
        r = svc.validate_before_send(_rec(status="rejected"))
        assert r.blocked is True

    def test_expired_status_blocked(self):
        r = svc.validate_before_send(_rec(status="expired"))
        assert r.blocked is True

    def test_blocked_status_blocked(self):
        r = svc.validate_before_send(_rec(status="blocked"))
        assert r.blocked is True

    def test_executed_blocked(self):
        r = svc.validate_before_send(_rec(status="executed"))
        assert r.blocked is True

    def test_failed_status_blocked(self):
        r = svc.validate_before_send(_rec(status="failed"))
        assert r.blocked is True

    def test_approved_allowed(self):
        r = svc.validate_before_send(_rec())
        assert r.blocked is False
        assert r.would_execute is True

    def test_already_executed_at(self):
        r = svc.validate_before_send(_rec(executed_at=datetime.now(UTC)))
        assert r.blocked is True
        assert r.blocked_reason == "already_executed"

    def test_already_failed_at(self):
        r = svc.validate_before_send(_rec(failed_at=datetime.now(UTC)))
        assert r.blocked is True
        assert r.blocked_reason == "previously_failed"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Expiration
# ═══════════════════════════════════════════════════════════════════════════════


class TestExpiration:
    def test_expired_approved_blocked(self):
        r = svc.validate_before_send(_rec(expires_minutes=-10))
        assert r.blocked is True
        assert r.blocked_reason == "expired"

    def test_not_expired_allowed(self):
        r = svc.validate_before_send(_rec(expires_minutes=30))
        assert r.blocked is False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Message safety
# ═══════════════════════════════════════════════════════════════════════════════


class TestMessageSafety:
    def test_empty_message_blocked(self):
        r = svc.validate_before_send(_rec(msg=""))
        assert r.blocked is True
        assert r.blocked_reason == "empty_message"

    def test_whitespace_message_blocked(self):
        r = svc.validate_before_send(_rec(msg="   "))
        assert r.blocked is True

    def test_missing_user_blocked(self):
        r = svc.validate_before_send(_rec(user_id=0))
        assert r.blocked is True
        assert r.blocked_reason == "missing_target_user"

    def test_token_blocked(self):
        r = svc.validate_before_send(_rec(msg="Use sk-abc123token"))
        assert r.blocked is True
        assert r.blocked_reason == "token_in_message"

    def test_bearer_token_blocked(self):
        r = svc.validate_before_send(_rec(msg="Bearer eyJhbGci"))
        assert r.blocked is True

    def test_raw_phone_blocked(self):
        r = svc.validate_before_send(_rec(msg="Call +998901234567"))
        assert r.blocked is True
        assert r.blocked_reason == "raw_phone_in_message"

    def test_fake_discount_blocked(self):
        r = svc.validate_before_send(_rec(msg="Sizga 20% chegirma!"))
        assert r.blocked is True
        assert r.blocked_reason == "fake_discount"

    def test_same_day_blocked(self):
        r = svc.validate_before_send(_rec(msg="Bugun qilamiz!"))
        assert r.blocked is True
        assert r.blocked_reason == "same_day_promise"

    def test_eng_arzon_blocked(self):
        r = svc.validate_before_send(_rec(msg="Eng arzon narxda"))
        assert r.blocked is True

    def test_safe_message_allowed(self):
        r = svc.validate_before_send(_rec(msg="Salom! Narx hisoblaymizmi?"))
        assert r.blocked is False

    def test_high_risk_user_dm_blocked(self):
        r = svc.validate_before_send(_rec(risk="high", channel="user_dm"))
        assert r.blocked is True
        assert r.blocked_reason == "high_risk_user_dm"

    def test_high_risk_admin_group_allowed(self):
        r = svc.validate_before_send(
            _rec(
                risk="high",
                channel="admin_group",
                action="send_admin_alert",
            )
        )
        assert r.blocked is False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Action validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestActionValidation:
    def test_send_user_reply_allowed(self):
        r = svc.validate_before_send(_rec(action="send_user_reply"))
        assert r.blocked is False

    def test_send_admin_alert_allowed(self):
        r = svc.validate_before_send(_rec(action="send_admin_alert"))
        assert r.blocked is False

    def test_handoff_allowed(self):
        r = svc.validate_before_send(_rec(action="handoff_operator"))
        assert r.blocked is False

    def test_unsendable_action_blocked(self):
        r = svc.validate_before_send(_rec(action="disable_agent"))
        assert r.blocked is True
        assert "unsendable" in (r.blocked_reason or "")

    def test_no_action_blocked(self):
        r = svc.validate_before_send(_rec(action="no_action"))
        assert r.blocked is True


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Send record
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendRecord:
    async def test_successful_send(self):
        bot = _bot(success=True)
        record = _rec()
        r = await svc.send_record(record, bot)
        assert r.would_execute is True
        assert r.status == "executed"
        bot.send_message.assert_called_once_with(
            chat_id=12345,
            text="Salom",
        )

    async def test_send_admin_alert(self):
        bot = _bot(success=True)
        record = _rec(action="send_admin_alert")
        r = await svc.send_record(record, bot, admin_chat_id=99999)
        assert r.would_execute is True
        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args
        assert call_args.kwargs.get("chat_id") == 99999

    async def test_send_failure(self):
        bot = _bot(success=False)
        record = _rec()
        r = await svc.send_record(record, bot)
        assert r.blocked is True
        assert "send_failed" in (r.blocked_reason or "")
        assert r.status == "failed"

    async def test_send_blocked_record(self):
        bot = _bot()
        record = _rec(status="proposed")
        r = await svc.send_record(record, bot)
        assert r.blocked is True
        bot.send_message.assert_not_called()

    async def test_send_expired_record(self):
        bot = _bot()
        record = _rec(expires_minutes=-5)
        r = await svc.send_record(record, bot)
        assert r.blocked is True
        bot.send_message.assert_not_called()

    async def test_bot_called_once_only(self):
        bot = _bot()
        record = _rec()
        await svc.send_record(record, bot)
        assert bot.send_message.call_count == 1

    async def test_error_sanitized(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock(
            side_effect=Exception("Error with sk-secret123token"),
        )
        record = _rec()
        r = await svc.send_record(record, bot)
        assert "sk-secret" not in (r.blocked_reason or "")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Process approved batch
# ═══════════════════════════════════════════════════════════════════════════════


class TestProcessApproved:
    async def test_sends_valid_records(self):
        bot = _bot()
        records = [_rec(execution_id="a"), _rec(execution_id="b")]
        results = await svc.process_approved(records, bot)
        assert len(results) == 2
        assert all(not r.blocked for _, r in results)

    async def test_skips_invalid(self):
        bot = _bot()
        records = [
            _rec(execution_id="ok"),
            _rec(execution_id="bad", msg=""),
        ]
        results = await svc.process_approved(records, bot)
        ok_results = [r for eid, r in results if eid == "ok"]
        bad_results = [r for eid, r in results if eid == "bad"]
        assert ok_results[0].blocked is False
        assert bad_results[0].blocked is True

    async def test_empty_list(self):
        bot = _bot()
        results = await svc.process_approved([], bot)
        assert results == []


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Safe payload / error sanitization
# ═══════════════════════════════════════════════════════════════════════════════


class TestSanitization:
    def test_build_safe_payload_redacts_phone(self):
        record = _rec(msg="Call +998901234567")
        safe = svc.build_safe_send_payload(record)
        assert "+998901234567" not in safe["message_text"]

    def test_build_safe_payload_redacts_token(self):
        record = _rec(msg="sk-abc123secret")
        safe = svc.build_safe_send_payload(record)
        assert "sk-abc" not in safe["message_text"]

    def test_sanitize_error_redacts_token(self):
        result = svc.sanitize_error("Error with sk-secret123 in response")
        assert "sk-secret" not in result

    def test_sanitize_error_truncates(self):
        long_err = "x" * 1000
        result = svc.sanitize_error(long_err)
        assert len(result) <= 500


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Message safety helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestMessageSafetyHelper:
    def test_clean_message_ok(self):
        blocked, reason = svc._check_message_safety("Salom!")
        assert blocked is False

    def test_empty_ok(self):
        blocked, reason = svc._check_message_safety("")
        assert blocked is False

    def test_token_detected(self):
        blocked, _ = svc._check_message_safety("token=abc123")
        assert blocked is True

    def test_phone_detected(self):
        blocked, _ = svc._check_message_safety("+998776655443")
        assert blocked is True

    def test_discount_detected(self):
        blocked, _ = svc._check_message_safety("50% off")
        assert blocked is True

    def test_same_day_detected(self):
        blocked, _ = svc._check_message_safety("bugun qilamiz")
        assert blocked is True

    def test_eng_arzon_detected(self):
        blocked, _ = svc._check_message_safety("eng arzon narx")
        assert blocked is True


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Scheduler job import
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchedulerJob:
    def test_job_importable(self):
        from apps.scheduler.jobs.approved_execution_sender_jobs import (
            process_approved_executions,
        )

        assert callable(process_approved_executions)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettings:
    def test_live_sender_default_false(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["agent_execution_live_sender_enabled"].default is False

    def test_batch_limit_default_10(self):
        from shared.config.settings import BusinessSettings

        assert (
            BusinessSettings.model_fields["agent_execution_live_sender_batch_limit"].default == 10
        )

    def test_revalidate_default_true(self):
        from shared.config.settings import BusinessSettings

        assert (
            BusinessSettings.model_fields["agent_execution_live_sender_revalidate"].default is True
        )

    def test_mark_failed_default_true(self):
        from shared.config.settings import BusinessSettings

        assert (
            BusinessSettings.model_fields[
                "agent_execution_live_sender_mark_failed_on_error"
            ].default
            is True
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Non-regression
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonRegression:
    def test_queue_service_still_works(self):
        from core.services.agent_execution_queue_service import (
            AgentExecutionQueueService,
        )

        assert callable(AgentExecutionQueueService.can_execute)

    def test_sandbox_still_works(self):
        from core.services.agent_execution_sandbox_service import (
            AgentExecutionSandboxService,
        )

        assert AgentExecutionSandboxService is not None

    def test_orchestrator_still_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        mem = {
            "followup_enabled": True,
            "memory_data": {},
            "lead_temperature": "warm",
            "telegram_user_id": 1,
        }
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"

    def test_signal_still_works(self):
        from core.services.lead_signal_service import LeadSignalService

        sig = LeadSignalService.extract_signals("kerak emas")
        assert sig.intent == "stop_request"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Duplicate prevention
# ═══════════════════════════════════════════════════════════════════════════════


class TestDuplicatePrevention:
    async def test_executed_at_set_blocks_resend(self):
        bot = _bot()
        record = _rec(executed_at=datetime.now(UTC))
        r = await svc.send_record(record, bot)
        assert r.blocked is True
        bot.send_message.assert_not_called()

    async def test_same_record_twice_first_ok(self):
        bot = _bot()
        record = _rec()
        r1 = await svc.send_record(record, bot)
        assert r1.blocked is False

    async def test_failed_record_not_resent(self):
        bot = _bot()
        record = _rec(failed_at=datetime.now(UTC))
        r = await svc.send_record(record, bot)
        assert r.blocked is True


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Handoff operator
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandoffOperator:
    async def test_handoff_sends_message(self):
        bot = _bot()
        record = _rec(action="handoff_operator")
        r = await svc.send_record(record, bot)
        assert r.would_execute is True
        bot.send_message.assert_called_once()

    async def test_handoff_empty_msg_blocked(self):
        r = svc.validate_before_send(_rec(action="handoff_operator", msg=""))
        assert r.blocked is True

    async def test_handoff_missing_user_blocked(self):
        r = svc.validate_before_send(
            _rec(action="handoff_operator", user_id=0),
        )
        assert r.blocked is True


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Admin alert details
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminAlertDetails:
    async def test_admin_alert_uses_admin_chat(self):
        bot = _bot()
        record = _rec(action="send_admin_alert", channel="admin_group")
        r = await svc.send_record(record, bot, admin_chat_id=88888)
        assert r.would_execute is True
        call_args = bot.send_message.call_args
        assert call_args.kwargs.get("chat_id") == 88888

    async def test_admin_alert_fallback_user_id(self):
        bot = _bot()
        record = _rec(action="send_admin_alert", user_id=77777)
        r = await svc.send_record(record, bot, admin_chat_id=None)
        assert r.would_execute is True
        call_args = bot.send_message.call_args
        assert call_args.kwargs.get("chat_id") == 77777

    async def test_admin_alert_no_message_check(self):
        r = svc.validate_before_send(
            _rec(
                action="send_admin_alert",
                msg="",
                channel="admin_group",
            )
        )
        assert r.blocked is False


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_safe_number_in_text_not_phone(self):
        r = svc.validate_before_send(_rec(msg="Narxi 5000000 so'm"))
        assert r.blocked is False

    def test_critical_risk_user_dm_blocked(self):
        r = svc.validate_before_send(_rec(risk="critical", channel="user_dm"))
        assert r.blocked is True

    def test_medium_risk_user_dm_allowed(self):
        r = svc.validate_before_send(_rec(risk="medium", channel="user_dm"))
        assert r.blocked is False

    def test_none_risk_allowed(self):
        r = svc.validate_before_send(_rec(risk="none"))
        assert r.blocked is False

    async def test_multiple_records_mixed(self):
        bot = _bot()
        records = [
            _rec(execution_id="good1"),
            _rec(execution_id="bad1", status="proposed"),
            _rec(execution_id="good2"),
            _rec(execution_id="bad2", msg="sk-secret"),
        ]
        results = await svc.process_approved(records, bot)
        assert len(results) == 4
        good = [r for eid, r in results if not r.blocked]
        bad = [r for eid, r in results if r.blocked]
        assert len(good) == 2
        assert len(bad) == 2

    def test_token_colon_blocked(self):
        r = svc.validate_before_send(_rec(msg="token:secret123"))
        assert r.blocked is True

    async def test_send_handoff_uses_user_id(self):
        bot = _bot()
        record = _rec(action="handoff_operator", user_id=55555)
        await svc.send_record(record, bot)
        call_args = bot.send_message.call_args
        assert call_args.kwargs.get("chat_id") == 55555

    def test_low_risk_admin_group_allowed(self):
        r = svc.validate_before_send(
            _rec(
                risk="low",
                channel="admin_group",
                action="send_admin_alert",
            )
        )
        assert r.blocked is False
