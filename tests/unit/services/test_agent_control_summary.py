"""Tests for build_agent_control_summary — pure function for F1 polish."""

from __future__ import annotations

from types import SimpleNamespace

from core.schemas.agent_control_center import (
    AgentControlSummary,
    AgentLastDecisionView,
)
from core.services.agent_control_center_service import (
    build_agent_control_summary,
)


def _settings(**business_kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(business=SimpleNamespace(**business_kwargs))


class TestEngineOnOffStatus:
    def test_engine_off_when_all_flags_false(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=False,
            agent_decision_engine_enabled=False,
        )
        summary = build_agent_control_summary(s)
        assert isinstance(summary, AgentControlSummary)
        assert summary.engine_on is False
        assert summary.status_pill_label == "ENGINE OFF"
        assert summary.status_pill_color == "gray"

    def test_engine_on_when_orchestrator_enabled(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_decision_engine_enabled=False,
        )
        summary = build_agent_control_summary(s)
        assert summary.engine_on is True
        assert "ENGINE ON" in summary.status_pill_label

    def test_engine_on_when_decision_engine_enabled(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=False,
            agent_decision_engine_enabled=True,
        )
        summary = build_agent_control_summary(s)
        assert summary.engine_on is True


class TestLogOnlyBadge:
    def test_log_only_true_when_both_log_only_flags_true(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=True,
            agent_decision_log_only=True,
        )
        summary = build_agent_control_summary(s)
        assert summary.log_only is True
        assert "LOG_ONLY" in summary.status_pill_label
        assert summary.status_pill_color == "blue"

    def test_log_only_false_when_orchestrator_log_only_false(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=False,
            agent_decision_log_only=True,
        )
        summary = build_agent_control_summary(s)
        assert summary.log_only is False


class TestLiveSendSafe:
    def test_live_send_safe_when_sender_off(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=False,
            agent_decision_log_only=False,
            agent_execution_live_sender_enabled=False,
            agent_execution_auto_execute_approved=False,
        )
        summary = build_agent_control_summary(s)
        assert summary.live_send_safe is True
        assert "Safe" in summary.safe_text
        assert "No live send" in summary.safe_text

    def test_live_send_unsafe_when_sender_on(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=False,
            agent_decision_log_only=False,
            agent_execution_live_sender_enabled=True,
            agent_execution_auto_execute_approved=False,
        )
        summary = build_agent_control_summary(s)
        assert summary.live_send_safe is False
        assert "LIVE" in summary.safe_text.upper()

    def test_live_send_unsafe_when_auto_execute_on(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=False,
            agent_decision_log_only=False,
            agent_execution_live_sender_enabled=False,
            agent_execution_auto_execute_approved=True,
        )
        summary = build_agent_control_summary(s)
        assert summary.live_send_safe is False


class TestStatusPillColors:
    def test_off_pill_is_gray(self) -> None:
        s = _settings(agent_response_orchestrator_enabled=False)
        assert build_agent_control_summary(s).status_pill_color == "gray"

    def test_log_only_pill_is_blue(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=True,
            agent_decision_log_only=True,
        )
        assert build_agent_control_summary(s).status_pill_color == "blue"

    def test_safe_live_pill_is_green(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=False,
            agent_decision_log_only=False,
            agent_execution_live_sender_enabled=False,
            agent_execution_auto_execute_approved=False,
        )
        assert build_agent_control_summary(s).status_pill_color == "green"

    def test_active_live_pill_is_red(self) -> None:
        s = _settings(
            agent_response_orchestrator_enabled=True,
            agent_response_orchestrator_log_only=False,
            agent_decision_log_only=False,
            agent_execution_live_sender_enabled=True,
            agent_execution_auto_execute_approved=True,
        )
        assert build_agent_control_summary(s).status_pill_color == "red"


class TestLastDecisionEmptyState:
    def test_empty_when_none_passed(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(s, last_decision=None)
        assert summary.last_decision is None
        assert "Hali agent qarorlari yo'q" in summary.empty_state_text

    def test_empty_when_empty_dict_passed(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(s, last_decision={})
        assert summary.last_decision is None


class TestLastDecisionPopulated:
    def test_populated_returns_view(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(
            s,
            last_decision={
                "decision_id": "d-123",
                "timestamp": "2026-05-29T10:00:00Z",
                "intent": "answer_pricing",
                "safety_flags": ["log_only", "no_send"],
                "execution_mode": "log_only",
            },
        )
        assert isinstance(summary.last_decision, AgentLastDecisionView)
        assert summary.last_decision.decision_id == "d-123"
        assert summary.last_decision.timestamp == "2026-05-29T10:00:00Z"
        assert summary.last_decision.intent == "answer_pricing"
        assert summary.last_decision.safety_flags == ("log_only", "no_send")
        assert summary.last_decision.execution_mode == "log_only"

    def test_safety_flags_normalised_from_string(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(
            s,
            last_decision={"safety_flags": "single_flag"},
        )
        assert summary.last_decision is not None
        assert summary.last_decision.safety_flags == ("single_flag",)

    def test_missing_keys_default_to_empty_string(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(s, last_decision={"intent": "x"})
        assert summary.last_decision is not None
        assert summary.last_decision.decision_id == ""
        assert summary.last_decision.timestamp == ""
        assert summary.last_decision.intent == "x"
        assert summary.last_decision.execution_mode == ""


class TestSecretRedaction:
    def test_no_token_leak_in_last_decision(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(
            s,
            last_decision={
                "decision_id": "d-1",
                "api_key": "sk-secret-1234567890",
                "bot_token": "12345:AAA-BBB",
            },
        )
        rendered = repr(summary)
        assert "sk-secret" not in rendered
        assert "AAA-BBB" not in rendered
        assert "api_key" not in rendered
        assert "bot_token" not in rendered

    def test_no_raw_prompt_leak_in_last_decision(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(
            s,
            last_decision={
                "decision_id": "d-1",
                "system_prompt": "You are Madina. Internal rules: ...",
                "user_message": "Salom, narx qancha?",
            },
        )
        rendered = repr(summary)
        assert "You are Madina" not in rendered
        assert "Internal rules" not in rendered
        assert "system_prompt" not in rendered
        assert "user_message" not in rendered

    def test_no_session_hash_or_internal_id_leaks(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(
            s,
            last_decision={
                "session_hash": "abcdef123456",
                "redis_key": "ai:state:42",
            },
        )
        rendered = repr(summary)
        assert "session_hash" not in rendered
        assert "abcdef123456" not in rendered
        assert "redis_key" not in rendered


class TestRobustness:
    def test_settings_without_business_attribute_does_not_crash(self) -> None:
        bare = SimpleNamespace()
        summary = build_agent_control_summary(bare)
        assert summary.engine_on is False

    def test_summary_is_frozen(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(s)
        try:
            summary.engine_on = True  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("AgentControlSummary should be frozen")

    def test_returns_correct_type(self) -> None:
        s = _settings()
        summary = build_agent_control_summary(s)
        assert isinstance(summary, AgentControlSummary)
