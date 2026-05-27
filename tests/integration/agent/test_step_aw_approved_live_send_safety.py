"""Step AW — APPROVED_LIVE_SEND safety integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from core.services.agent_effective_settings_service import AgentEffectiveSettingsService
from core.services.agent_rollout_preset_service import AgentRolloutPresetService
from core.services.approved_execution_sender_service import ApprovedExecutionSenderService


def _live_send_overrides():
    return AgentRolloutPresetService.build_preset_settings("approved_live_send")


def _effective():
    s = AgentEffectiveSettingsService(_live_send_overrides())
    s._runtime_enabled = True
    return s


def _rec(
    *,
    status="approved",
    msg="Salom!",
    user_id=123,
    risk="low",
    channel="user_dm",
    action="send_user_reply",
    expires_minutes=30,
    executed_at=None,
    failed_at=None,
    execution_id="test-001",
):
    now = datetime.now(UTC)
    r = MagicMock()
    r.execution_id = execution_id
    r.telegram_user_id = user_id
    r.action = action
    r.mode = "live"
    r.status = status
    r.risk_level = risk
    r.channel = channel
    r.payload_json = {"message_text": msg, "admin_alert_text": msg}
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


class TestPresetFlags:
    def test_requires_allow_live(self):
        r = AgentRolloutPresetService.preview_preset("approved_live_send", {})
        assert not r.allowed

    def test_allowed_with_flag(self):
        r = AgentRolloutPresetService.preview_preset(
            "approved_live_send", {}, allow_live_flags=True
        )
        assert r.allowed

    def test_live_sender_enabled(self):
        assert _effective().get_execution_settings().live_sender_enabled is True

    def test_auto_execute_enabled(self):
        assert _effective().get_execution_settings().auto_execute_approved is True

    def test_queue_enabled(self):
        assert _effective().get_execution_settings().queue_enabled is True

    def test_sandbox_enabled(self):
        assert _effective().get_execution_settings().sandbox_enabled is True


class TestSendApproved:
    async def test_approved_sends(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value=MagicMock())
        r = await ApprovedExecutionSenderService.send_record(_rec(), bot)
        assert r.would_execute is True
        bot.send_message.assert_called_once()

    async def test_executed_at_set(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(_rec(), bot)
        assert r.status == "executed"


class TestNoSendStatuses:
    async def test_proposed_no_send(self):
        bot = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(_rec(status="proposed"), bot)
        assert r.blocked is True
        bot.send_message.assert_not_called()

    async def test_rejected_no_send(self):
        bot = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(_rec(status="rejected"), bot)
        assert r.blocked is True

    async def test_expired_no_send(self):
        bot = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(_rec(status="expired"), bot)
        assert r.blocked is True

    async def test_blocked_no_send(self):
        bot = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(_rec(status="blocked"), bot)
        assert r.blocked is True

    async def test_executed_no_resend(self):
        bot = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(
            _rec(executed_at=datetime.now(UTC)), bot
        )
        assert r.blocked is True

    async def test_failed_no_resend(self):
        bot = AsyncMock()
        r = await ApprovedExecutionSenderService.send_record(_rec(failed_at=datetime.now(UTC)), bot)
        assert r.blocked is True


class TestSafetyBlocks:
    def test_token_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(msg="sk-secret123"))
        assert r.blocked is True

    def test_phone_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(msg="+998901234567"))
        assert r.blocked is True

    def test_fake_discount_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(msg="20% chegirma!"))
        assert r.blocked is True

    def test_same_day_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(msg="Bugun qilamiz!"))
        assert r.blocked is True

    def test_high_risk_user_dm_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(risk="high"))
        assert r.blocked is True

    def test_empty_message_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(msg=""))
        assert r.blocked is True

    def test_missing_user_blocked(self):
        r = ApprovedExecutionSenderService.validate_before_send(_rec(user_id=0))
        assert r.blocked is True


class TestBotError:
    async def test_exception_marks_failed(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=Exception("network"))
        r = await ApprovedExecutionSenderService.send_record(_rec(), bot)
        assert r.status == "failed"

    async def test_error_sanitized(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=Exception("sk-secret err"))
        r = await ApprovedExecutionSenderService.send_record(_rec(), bot)
        assert "sk-secret" not in (r.blocked_reason or "")


class TestBatchProcess:
    async def test_skips_invalid(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        results = await ApprovedExecutionSenderService.process_approved(
            [_rec(execution_id="ok"), _rec(execution_id="bad", msg="")], bot
        )
        ok = [r for eid, r in results if not r.blocked]
        bad = [r for eid, r in results if r.blocked]
        assert len(ok) == 1 and len(bad) == 1


class TestRollback:
    def test_off_disables(self):
        off = AgentRolloutPresetService.build_preset_settings("off")
        s = AgentEffectiveSettingsService(off)
        s._runtime_enabled = True
        e = s.get_execution_settings()
        assert not e.live_sender_enabled and not e.auto_execute_approved
