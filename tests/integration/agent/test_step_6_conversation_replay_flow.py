"""Integration tests for conversation replay flow — Step 6."""

from __future__ import annotations

from core.services.crm_conversation_replay_service import (
    build_replay,
    sanitize_metadata,
    sanitize_preview,
)


class TestPriceHandoffScenario:
    def test_price_plus_handoff_replay(self) -> None:
        contact = {"id": 10, "phone": "+998901234567"}
        messages = [
            {
                "direction": "inbound",
                "text": "Salom, narx qancha?",
                "created_at": "2025-01-01T10:00",
            },
            {
                "direction": "outbound",
                "sender_type": "bot",
                "text": "Salom! 80,000-140,000 UZS/m²",
                "created_at": "2025-01-01T10:00:05",
            },
            {
                "direction": "inbound",
                "text": "operator chaqiring",
                "created_at": "2025-01-01T10:01",
            },
        ]
        traces = [{"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-01T10:00:05"}]
        handoffs = [{"id": 1, "status": "pending", "created_at": "2025-01-01T10:01:10"}]
        result = build_replay(contact, messages, traces, handoffs)
        assert result.summary.user_messages >= 2
        assert result.summary.price_events >= 1
        assert result.summary.handoff_events >= 1
        types = {e.event_type for e in result.events}
        assert "user_message" in types
        assert "price_estimate" in types
        assert "handoff_requested" in types
        assert "phone_shared" in types

    def test_price_handoff_events_sorted(self) -> None:
        contact = {"id": 11}
        messages = [
            {"direction": "inbound", "text": "narx?", "created_at": "2025-01-01T10:00"},
        ]
        handoffs = [{"id": 2, "status": "pending", "created_at": "2025-01-01T10:05"}]
        result = build_replay(contact, messages, handoffs=handoffs)
        timestamps = [e.timestamp for e in result.events if e.timestamp]
        assert timestamps == sorted(timestamps)


class TestObjectionScenario:
    def test_objection_appears_in_replay(self) -> None:
        contact = {"id": 20}
        messages = [
            {"direction": "inbound", "text": "bu juda qimmat", "created_at": "2025-01-01T10:00"},
        ]
        result = build_replay(contact, messages)
        obj_events = [e for e in result.events if e.event_type == "objection_detected"]
        assert len(obj_events) >= 1

    def test_objection_from_trace(self) -> None:
        contact = {"id": 21}
        traces = [{"objection_type": "price", "timestamp": "2025-01-01T10:00"}]
        result = build_replay(contact, traces=traces)
        obj_events = [e for e in result.events if e.event_type == "objection_detected"]
        assert len(obj_events) >= 1

    def test_delay_objection(self) -> None:
        contact = {"id": 22}
        messages = [
            {"direction": "inbound", "text": "keyinroq qilamiz", "created_at": "2025-01-01T10:00"},
        ]
        result = build_replay(contact, messages)
        obj_events = [e for e in result.events if e.event_type == "objection_detected"]
        assert len(obj_events) >= 1


class TestStopScenario:
    def test_stop_appears(self) -> None:
        contact = {"id": 30}
        messages = [
            {"direction": "inbound", "text": "kerak emas rahmat", "created_at": "2025-01-01T10:00"},
        ]
        result = build_replay(contact, messages)
        stop_events = [e for e in result.events if e.event_type == "stop_requested"]
        assert len(stop_events) >= 1

    def test_stop_recommendation(self) -> None:
        contact = {"id": 31}
        messages = [
            {"direction": "inbound", "text": "kerak emas", "created_at": "2025-01-01T10:00"},
        ]
        result = build_replay(contact, messages)
        assert (
            "to'xtatdi" in result.summary.recommended_next_action.lower()
            or "ulanmang" in result.summary.recommended_next_action.lower()
        )


class TestEmptyContact:
    def test_empty_renders(self) -> None:
        result = build_replay(contact={"id": 40})
        assert result.events == []
        assert result.summary.total_events == 0

    def test_empty_recommended_action(self) -> None:
        result = build_replay(contact={"id": 41})
        assert result.summary.recommended_next_action != ""


class TestNoExternalCalls:
    def test_no_telegram_send(self) -> None:
        import core.services.crm_conversation_replay_service as svc

        source = open(svc.__file__, encoding="utf-8").read()
        assert "send_message" not in source
        assert "Bot(" not in source

    def test_no_openai_call(self) -> None:
        import core.services.crm_conversation_replay_service as svc

        source = open(svc.__file__, encoding="utf-8").read()
        assert "import openai" not in source
        assert "ChatCompletion" not in source
        assert "OpenAI(" not in source

    def test_no_token_in_service(self) -> None:
        import core.services.crm_conversation_replay_service as svc

        source = open(svc.__file__, encoding="utf-8").read()
        assert "BOT_TOKEN" not in source
        assert "os.environ" not in source
        assert "get_secret_value" not in source


class TestPrivacySanitization:
    def test_preview_redacts_secrets(self) -> None:
        result = sanitize_preview("my key sk-abc123def456ghij and Bearer tok_xyz1234567890")
        assert "sk-abc123def456ghij" not in (result or "")
        assert "tok_xyz1234567890" not in (result or "")

    def test_metadata_strips_unsafe(self) -> None:
        result = sanitize_metadata(
            {"intent": "price", "raw_prompt": "system prompt text", "password": "secret"}
        )
        assert "intent: price" in (result or "")
        assert "secret" not in (result or "")
        assert "system prompt" not in (result or "")
