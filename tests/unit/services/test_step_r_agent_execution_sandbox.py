"""Tests for Step R — AgentExecutionSandboxService."""

from __future__ import annotations

from core.schemas.agent_execution import AgentExecutionPayload
from core.services.agent_execution_sandbox_service import AgentExecutionSandboxService

svc = AgentExecutionSandboxService


def _mem(
    *,
    followup_enabled: bool = True,
    stop_reason: str | None = None,
    temp: str = "warm",
    state: str = "new_visitor",
    followup_count: int = 0,
    daily_count: int = 0,
    user_id: int = 12345,
) -> dict:
    md: dict = {"customer_state": state, "daily_action_count": daily_count}
    m: dict = {
        "followup_enabled": followup_enabled,
        "lead_temperature": temp,
        "followup_count": followup_count,
        "memory_data": md,
        "telegram_user_id": user_id,
    }
    if stop_reason:
        m["stop_reason"] = stop_reason
    return m


def _payload(
    action: str = "send_user_reply",
    msg: str = "Hello",
    channel: str = "user_dm",
    user_id: int = 12345,
) -> dict:
    return {
        "action": action,
        "channel": channel,
        "user_message_text": msg,
        "target_user_id": user_id,
    }


# ─── 1. Modes ───────────────────────────────────────────────────────────────


class TestLogOnlyMode:
    def test_log_only_no_execute(self):
        ex = svc.prepare_execution(_payload(), _mem(), "log_only")
        r = svc.validate_execution(ex, _mem())
        assert r.would_execute is False
        assert r.blocked is False
        assert r.status == "proposed"

    def test_log_only_safe(self):
        ex = svc.prepare_execution(_payload(), _mem(), "log_only")
        r = svc.validate_execution(ex, _mem())
        assert r.safe_to_execute is True


class TestDryRunMode:
    def test_dry_run_valid(self):
        ex = svc.prepare_execution(_payload(), _mem(), "dry_run")
        r = svc.validate_execution(ex, _mem())
        assert r.would_execute is True
        assert r.blocked is False
        assert r.safe_to_execute is True

    def test_dry_run_blocked(self):
        ex = svc.prepare_execution(
            _payload(msg=""),
            _mem(),
            "dry_run",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.would_execute is False


class TestCanaryMode:
    def test_canary_user_allowed(self):
        ex = svc.prepare_execution(_payload(user_id=111), _mem(user_id=111), "canary")
        r = svc.validate_execution(ex, _mem(user_id=111), canary_user_ids=[111])
        assert r.would_execute is True
        assert r.status == "approved"

    def test_non_canary_blocked(self):
        ex = svc.prepare_execution(_payload(user_id=222), _mem(user_id=222), "canary")
        r = svc.validate_execution(ex, _mem(user_id=222), canary_user_ids=[111])
        assert r.blocked is True
        assert r.blocked_reason == "non_canary_user"

    def test_canary_empty_list(self):
        ex = svc.prepare_execution(_payload(), _mem(), "canary")
        r = svc.validate_execution(ex, _mem(), canary_user_ids=[])
        assert r.blocked is True


class TestApprovalMode:
    def test_approval_required(self):
        ex = svc.prepare_execution(_payload(), _mem(), "approval_required")
        r = svc.validate_execution(ex, _mem())
        assert r.requires_approval is True
        assert r.would_execute is False
        assert r.status == "proposed"


class TestLiveMode:
    def test_live_safe_allowed(self):
        ex = svc.prepare_execution(_payload(), _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.would_execute is True
        assert r.safe_to_execute is True
        assert r.status == "approved"

    def test_live_blocked_by_safety(self):
        ex = svc.prepare_execution(
            _payload(msg="sk-secret123token"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True


# ─── 2. Safety blocks ───────────────────────────────────────────────────────


class TestSafetyBlocks:
    def test_followup_disabled(self):
        ex = svc.prepare_execution(_payload(), _mem(followup_enabled=False), "live")
        r = svc.validate_execution(ex, _mem(followup_enabled=False))
        assert r.blocked is True
        assert "followup_disabled" in (r.blocked_reason or "")

    def test_stop_reason_user_opted_out(self):
        m = _mem(followup_enabled=False, stop_reason="user_opted_out")
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True
        assert "user_opted_out" in (r.blocked_reason or "")

    def test_stop_reason_deal_closed(self):
        m = _mem(followup_enabled=False, stop_reason="deal_closed")
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_stop_reason_lost(self):
        m = _mem(followup_enabled=False, stop_reason="lost_lead")
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_terminal_state_stopped(self):
        m = _mem(state="stopped")
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_terminal_state_lost(self):
        m = _mem(state="lost")
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_terminal_state_closed(self):
        m = _mem(state="closed")
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_empty_message(self):
        ex = svc.prepare_execution(_payload(msg=""), _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "empty_message"

    def test_whitespace_only_message(self):
        ex = svc.prepare_execution(_payload(msg="   "), _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "empty_message"

    def test_missing_target_user(self):
        ex = svc.prepare_execution(_payload(user_id=0), _mem(), "live")
        # user_id=0 is falsy
        blocked, reason = svc.should_block(
            AgentExecutionPayload(
                execution_id="test",
                mode="live",
                status="proposed",
                action="send_user_reply",
                target_user_id=None,
                channel="user_dm",
                message_text="hi",
            ),
            _mem(),
        )
        assert blocked is True
        assert reason == "missing_target_user"

    def test_token_in_message(self):
        ex = svc.prepare_execution(
            _payload(msg="Here is sk-abc123secret key"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "token_in_message"

    def test_raw_phone_in_message(self):
        ex = svc.prepare_execution(
            _payload(msg="Call +998901234567"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "raw_phone_in_message"

    def test_fake_discount(self):
        ex = svc.prepare_execution(
            _payload(msg="Sizga 20% chegirma!"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "fake_discount_in_message"

    def test_same_day_promise(self):
        ex = svc.prepare_execution(
            _payload(msg="Bugun qilamiz albatta"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "same_day_promise"

    def test_eng_arzon_claim(self):
        ex = svc.prepare_execution(
            _payload(msg="Eng arzon narxda beramiz"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "eng_arzon_claim"

    def test_high_risk_user_dm(self):
        m = _mem(followup_count=5)
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True
        assert r.blocked_reason == "high_risk_user_dm"

    def test_daily_cap_reached(self):
        m = _mem(daily_count=3)
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True
        assert r.blocked_reason == "daily_cap_reached"


# ─── 3. Approval ────────────────────────────────────────────────────────────


class TestApproval:
    def test_approve(self):
        ex = svc.prepare_execution(_payload(), _mem(), "approval_required")
        approved = svc.approve_execution(ex, admin_id=999)
        assert approved.status == "approved"
        assert approved.approved_by == 999

    def test_reject(self):
        ex = svc.prepare_execution(_payload(), _mem(), "approval_required")
        rejected = svc.reject_execution(ex, admin_id=999, reason="not safe")
        assert rejected.status == "rejected"
        assert rejected.blocked_reason == "not safe"

    def test_requires_approval_user_dm(self):
        assert (
            svc.requires_approval(
                "send_user_reply",
                "user_dm",
                "approval_required",
            )
            is True
        )

    def test_no_approval_admin_alert(self):
        assert (
            svc.requires_approval(
                "send_admin_alert",
                "admin_group",
                "approval_required",
            )
            is False
        )

    def test_no_approval_live_mode(self):
        assert (
            svc.requires_approval(
                "send_user_reply",
                "user_dm",
                "live",
            )
            is False
        )


# ─── 4. Rollback ────────────────────────────────────────────────────────────


class TestRollback:
    def test_rollback_safe(self):
        ex = svc.prepare_execution(_payload(), _mem(), "live")
        rolled = svc.rollback_execution(ex)
        assert rolled.status == "rolled_back"
        assert rolled.rollback_action == "noop"


# ─── 5. Trace ───────────────────────────────────────────────────────────────


class TestTrace:
    def test_store_trace(self):
        ex = svc.prepare_execution(_payload(), _mem(), "dry_run")
        r = svc.validate_execution(ex, _mem())
        md = svc.store_execution_trace({}, ex, r)
        stored = md["last_execution_sandbox"]
        assert stored["mode"] == "dry_run"
        assert stored["would_execute"] is True
        assert "created_at" in stored

    def test_trace_preserves_existing(self):
        ex = svc.prepare_execution(_payload(), _mem(), "log_only")
        r = svc.validate_execution(ex, _mem())
        md = svc.store_execution_trace({"key": 42}, ex, r)
        assert md["key"] == 42


# ─── 6. Risk assessment ─────────────────────────────────────────────────────


class TestRiskAssessment:
    def test_cold_user_dm_medium(self):
        ex = svc.prepare_execution(_payload(), _mem(temp="cold"), "live")
        assert ex.risk_level == "medium"

    def test_warm_user_dm_low(self):
        ex = svc.prepare_execution(_payload(), _mem(temp="warm"), "live")
        assert ex.risk_level == "low"

    def test_admin_alert_none(self):
        ex = svc.prepare_execution(
            _payload(action="send_admin_alert", channel="admin_group"),
            _mem(),
            "live",
        )
        assert ex.risk_level == "none"

    def test_high_followup_count_high(self):
        ex = svc.prepare_execution(_payload(), _mem(followup_count=5), "live")
        assert ex.risk_level == "high"


# ─── 7. Canary user detection ───────────────────────────────────────────────


class TestCanaryUser:
    def test_in_list(self):
        assert svc.is_canary_user(111, [111, 222]) is True

    def test_not_in_list(self):
        assert svc.is_canary_user(333, [111, 222]) is False

    def test_empty_list(self):
        assert svc.is_canary_user(111, []) is False

    def test_none_list(self):
        assert svc.is_canary_user(111, None) is False

    def test_none_user(self):
        assert svc.is_canary_user(None, [111]) is False


# ─── 8. Prepare execution ───────────────────────────────────────────────────


class TestPrepareExecution:
    def test_generates_id(self):
        ex = svc.prepare_execution(_payload(), _mem(), "live")
        assert ex.execution_id
        assert len(ex.execution_id) > 0

    def test_mode_set(self):
        ex = svc.prepare_execution(_payload(), _mem(), "canary")
        assert ex.mode == "canary"

    def test_status_proposed(self):
        ex = svc.prepare_execution(_payload(), _mem(), "live")
        assert ex.status == "proposed"

    def test_target_from_memory(self):
        ex = svc.prepare_execution(
            {"action": "send_user_reply", "user_message_text": "hi"},
            _mem(user_id=999),
            "live",
        )
        assert ex.target_user_id == 999


# ─── 9. Admin alert sandbox ─────────────────────────────────────────────────


class TestAdminAlertSandbox:
    def test_admin_alert_not_blocked(self):
        p = {
            "action": "send_admin_alert",
            "channel": "admin_group",
            "admin_alert_text": "Alert!",
            "user_message_text": "",
        }
        ex = svc.prepare_execution(p, _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False

    def test_admin_alert_risk_none(self):
        p = {"action": "send_admin_alert", "channel": "admin_group"}
        ex = svc.prepare_execution(p, _mem(), "live")
        assert ex.risk_level == "none"


# ─── 10. Edge cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_unknown_mode_blocked(self):
        ex = AgentExecutionPayload(
            execution_id="test",
            mode="unknown_mode",
            status="proposed",
            action="send_user_reply",
            target_user_id=123,
            channel="user_dm",
            message_text="hi",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True
        assert r.blocked_reason == "unknown_mode"

    def test_safe_message_passes(self):
        ex = svc.prepare_execution(
            _payload(msg="Salom, yordam kerakmi?"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False
        assert r.would_execute is True

    def test_disable_agent_action_ok(self):
        p = {"action": "disable_agent", "channel": "none", "user_message_text": "Tushunarli"}
        ex = svc.prepare_execution(p, _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False


# ─── 11. Schema immutability ────────────────────────────────────────────────


class TestImmutability:
    def test_payload_frozen(self):
        import pytest

        ex = svc.prepare_execution(_payload(), _mem(), "live")
        with pytest.raises(AttributeError):
            ex.mode = "other"  # type: ignore[misc]

    def test_result_frozen(self):
        import pytest

        ex = svc.prepare_execution(_payload(), _mem(), "dry_run")
        r = svc.validate_execution(ex, _mem())
        with pytest.raises(AttributeError):
            r.blocked = True  # type: ignore[misc]


# ─── 12. Additional safety scenarios ────────────────────────────────────────


class TestAdditionalSafety:
    def test_bearer_token_blocked(self):
        ex = svc.prepare_execution(
            _payload(msg="Use Bearer abc123xyz for access"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True

    def test_token_equals_blocked(self):
        ex = svc.prepare_execution(
            _payload(msg="token=abc123"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is True

    def test_safe_number_not_phone(self):
        ex = svc.prepare_execution(
            _payload(msg="20 m2 narxi 5000000 so'm"),
            _mem(),
            "live",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False

    def test_multiple_safety_first_wins(self):
        m = _mem(followup_enabled=False, stop_reason="user_opted_out")
        ex = svc.prepare_execution(_payload(msg="sk-token"), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_daily_cap_4_blocked(self):
        m = _mem(daily_count=4)
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_daily_cap_2_allowed(self):
        m = _mem(daily_count=2)
        ex = svc.prepare_execution(_payload(), m, "live")
        r = svc.validate_execution(ex, m)
        assert r.blocked is False

    def test_schedule_followup_not_blocked_by_empty_msg(self):
        p = {"action": "schedule_followup", "channel": "user_dm", "user_message_text": ""}
        ex = svc.prepare_execution(p, _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False

    def test_cancel_followups_safe(self):
        p = {"action": "cancel_followups", "channel": "none", "user_message_text": ""}
        ex = svc.prepare_execution(p, _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False


# ─── 13. Mode combinations ──────────────────────────────────────────────────


class TestModeCombinations:
    def test_dry_run_with_high_risk(self):
        m = _mem(followup_count=5)
        ex = svc.prepare_execution(_payload(), m, "dry_run")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_canary_with_blocked_message(self):
        ex = svc.prepare_execution(
            _payload(msg="sk-secret", user_id=111),
            _mem(user_id=111),
            "canary",
        )
        r = svc.validate_execution(ex, _mem(user_id=111), canary_user_ids=[111])
        assert r.blocked is True

    def test_log_only_still_validates_terminal(self):
        m = _mem(followup_enabled=False, stop_reason="deal_closed")
        ex = svc.prepare_execution(_payload(), m, "log_only")
        r = svc.validate_execution(ex, m)
        assert r.blocked is True

    def test_live_admin_alert_safe_msg(self):
        p = {
            "action": "send_admin_alert",
            "channel": "admin_group",
            "admin_alert_text": "New hot lead!",
        }
        ex = svc.prepare_execution(p, _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.would_execute is True

    def test_dry_run_normal_safe(self):
        ex = svc.prepare_execution(
            _payload(msg="Salom! Narx hisoblaymizmi?"),
            _mem(),
            "dry_run",
        )
        r = svc.validate_execution(ex, _mem())
        assert r.would_execute is True
        assert r.safe_to_execute is True

    def test_live_handoff_operator(self):
        p = {
            "action": "handoff_operator",
            "channel": "user_dm",
            "user_message_text": "Operatorga ulaymiz",
        }
        ex = svc.prepare_execution(p, _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        assert r.blocked is False

    def test_canary_multiple_users(self):
        canary = [100, 200, 300]
        ex1 = svc.prepare_execution(_payload(user_id=100), _mem(user_id=100), "canary")
        r1 = svc.validate_execution(ex1, _mem(user_id=100), canary_user_ids=canary)
        assert r1.would_execute is True

        ex2 = svc.prepare_execution(_payload(user_id=999), _mem(user_id=999), "canary")
        r2 = svc.validate_execution(ex2, _mem(user_id=999), canary_user_ids=canary)
        assert r2.blocked is True


# ─── 14. Trace completeness ─────────────────────────────────────────────────


class TestTraceCompleteness:
    def test_trace_has_mode(self):
        ex = svc.prepare_execution(_payload(), _mem(), "canary")
        r = svc.validate_execution(ex, _mem(), canary_user_ids=[12345])
        md = svc.store_execution_trace({}, ex, r)
        assert md["last_execution_sandbox"]["mode"] == "canary"

    def test_trace_has_action(self):
        ex = svc.prepare_execution(_payload(), _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        md = svc.store_execution_trace({}, ex, r)
        assert md["last_execution_sandbox"]["action"] == "send_user_reply"

    def test_blocked_trace_has_reason(self):
        ex = svc.prepare_execution(_payload(msg=""), _mem(), "live")
        r = svc.validate_execution(ex, _mem())
        md = svc.store_execution_trace({}, ex, r)
        assert md["last_execution_sandbox"]["blocked"] is True
        assert md["last_execution_sandbox"]["blocked_reason"] == "empty_message"

    def test_trace_has_risk(self):
        ex = svc.prepare_execution(_payload(), _mem(temp="cold"), "live")
        r = svc.validate_execution(ex, _mem(temp="cold"))
        md = svc.store_execution_trace({}, ex, r)
        assert md["last_execution_sandbox"]["risk_level"] == "medium"


# ─── 15. Execution IDs ──────────────────────────────────────────────────────


class TestExecutionIds:
    def test_unique_ids(self):
        ex1 = svc.prepare_execution(_payload(), _mem(), "live")
        ex2 = svc.prepare_execution(_payload(), _mem(), "live")
        assert ex1.execution_id != ex2.execution_id

    def test_id_preserved_on_approve(self):
        ex = svc.prepare_execution(_payload(), _mem(), "approval_required")
        approved = svc.approve_execution(ex, admin_id=1)
        assert approved.execution_id == ex.execution_id

    def test_id_preserved_on_reject(self):
        ex = svc.prepare_execution(_payload(), _mem(), "approval_required")
        rejected = svc.reject_execution(ex, admin_id=1, reason="no")
        assert rejected.execution_id == ex.execution_id

    def test_id_preserved_on_rollback(self):
        ex = svc.prepare_execution(_payload(), _mem(), "live")
        rolled = svc.rollback_execution(ex)
        assert rolled.execution_id == ex.execution_id


# ─── 16. Default disabled behavior ──────────────────────────────────────────


class TestDefaultDisabled:
    def test_sandbox_service_importable(self):
        from infrastructure.di import get_agent_execution_sandbox_service

        s = get_agent_execution_sandbox_service()
        assert s is not None

    def test_existing_orchestrator_unchanged(self):
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
