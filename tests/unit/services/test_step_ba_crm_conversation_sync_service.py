"""Tests for Step BA — CRMConversationSyncService."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.services.crm_conversation_sync_service import CRMConversationSyncService

svc = CRMConversationSyncService
NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
T = lambda min_ago: NOW - timedelta(minutes=min_ago)

class TestAnsweredStatus:
    def test_stopped_not_unanswered(self):
        r = svc.compute_answered_status(T(10), None, None, "stopped")
        assert not r["is_unanswered"]

    def test_lost_not_unanswered(self):
        r = svc.compute_answered_status(T(10), None, None, "lost")
        assert not r["is_unanswered"]

    def test_won_not_unanswered(self):
        r = svc.compute_answered_status(T(10), None, None, "won")
        assert not r["is_unanswered"]

    def test_no_inbound(self):
        r = svc.compute_answered_status(None, None, None)
        assert not r["is_unanswered"]

    def test_unanswered(self):
        r = svc.compute_answered_status(T(10), None, None)
        assert r["is_unanswered"]

    def test_bot_reply_answers(self):
        r = svc.compute_answered_status(T(10), T(5), None)
        assert not r["is_unanswered"]
        assert r["answered_by"] == "bot"

    def test_operator_reply_answers(self):
        r = svc.compute_answered_status(T(10), None, T(5))
        assert not r["is_unanswered"]
        assert r["answered_by"] == "operator"

    def test_operator_wins_if_newer(self):
        r = svc.compute_answered_status(T(10), T(8), T(5))
        assert r["answered_by"] == "operator"

    def test_bot_wins_if_newer(self):
        r = svc.compute_answered_status(T(10), T(3), T(5))
        assert r["answered_by"] == "bot"

    def test_inbound_after_reply_unanswered(self):
        r = svc.compute_answered_status(T(2), T(5), T(8))
        assert r["is_unanswered"]

    def test_reply_same_time_answered(self):
        r = svc.compute_answered_status(T(10), T(10), None)
        assert not r["is_unanswered"]

class TestResponseTime:
    def test_basic(self):
        assert svc.calculate_response_time_seconds(T(10), T(5)) == 300

    def test_instant(self):
        assert svc.calculate_response_time_seconds(T(5), T(5)) == 0

    def test_no_negative(self):
        assert svc.calculate_response_time_seconds(T(5), T(10)) == 0

class TestClassifyEvent:
    def test_user_text(self):
        assert svc.classify_event_type("inbound", "user", "text") == "user_message"
    def test_bot_reply(self):
        assert svc.classify_event_type("outbound", "bot") == "bot_reply"
    def test_operator_reply(self):
        assert svc.classify_event_type("outbound", "operator") == "operator_reply"
    def test_agent_trace(self):
        assert svc.classify_event_type("agent_trace", "agent") == "agent_trace"
    def test_callback(self):
        assert svc.classify_event_type("inbound", "user", "callback") == "callback"
    def test_photo(self):
        assert svc.classify_event_type("inbound", "user", "photo") == "photo"
    def test_voice(self):
        assert svc.classify_event_type("inbound", "user", "voice") == "voice"
    def test_document(self):
        assert svc.classify_event_type("inbound", "user", "document") == "document"
    def test_system(self):
        assert svc.classify_event_type("system", "system") == "system"

class TestIsAnswering:
    def test_bot_outbound_yes(self):
        assert svc.is_answering_event("outbound", "bot")
    def test_operator_outbound_yes(self):
        assert svc.is_answering_event("outbound", "operator")
    def test_agent_trace_no(self):
        assert not svc.is_answering_event("agent_trace", "agent")
    def test_system_no(self):
        assert not svc.is_answering_event("system", "system")
    def test_inbound_no(self):
        assert not svc.is_answering_event("inbound", "user")

class TestRedaction:
    def test_phone(self):
        assert "+998" not in svc.redact_text("+998901234567")
    def test_token(self):
        assert "sk-" not in svc.redact_text("sk-abc123secret")
    def test_clean(self):
        assert svc.redact_text("salom") == "salom"

class TestSanitizePayload:
    def test_token_removed(self):
        r = svc.sanitize_payload({"key": "sk-secret123"})
        assert "sk-secret" not in str(r)
    def test_none(self):
        assert svc.sanitize_payload(None) is None
    def test_clean(self):
        assert svc.sanitize_payload({"a": "b"}) == {"a": "b"}

class TestSummary:
    def test_unanswered(self):
        r = svc.build_conversation_summary(T(10), None, None)
        assert r["is_unanswered"]
        assert r["unanswered_minutes"] is not None

    def test_answered_by_bot(self):
        r = svc.build_conversation_summary(T(10), T(5), None)
        assert not r["is_unanswered"]
        assert r["answered_by"] == "bot"

    def test_no_inbound(self):
        r = svc.build_conversation_summary(None, None, None)
        assert not r["is_unanswered"]

    def test_stopped(self):
        r = svc.build_conversation_summary(T(10), None, None, "stopped")
        assert not r["is_unanswered"]

    def test_timeline_counts(self):
        r = svc.build_conversation_summary(T(10), T(5), None,
            timeline_counts={"user_message": 5, "bot_reply": 3})
        assert r["timeline_counts"]["user_message"] == 5
