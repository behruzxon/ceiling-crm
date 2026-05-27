"""Tests for conversation replay service — Step 6."""

from __future__ import annotations

from core.schemas.crm_conversation_replay import (
    ConversationReplayEvent,
    ConversationReplayResult,
)
from core.services.crm_conversation_replay_service import (
    ICON_MAP,
    VALID_EVENT_TYPES,
    build_handoff_event,
    build_intent_event,
    build_objection_event,
    build_phone_event,
    build_price_event,
    build_replay,
    build_stop_event,
    build_summary,
    classify_message_event,
    detect_intent,
    mask_phone_in_text,
    sanitize_metadata,
    sanitize_preview,
    sort_events_chronologically,
)


class TestBuildReplay:
    def test_empty_replay(self) -> None:
        result = build_replay(contact={"id": 1})
        assert isinstance(result, ConversationReplayResult)
        assert result.contact_id == 1
        assert result.events == []
        assert result.summary.total_events == 0

    def test_replay_with_messages(self) -> None:
        msgs = [
            {"direction": "inbound", "text": "Salom", "created_at": "2025-01-01T10:00:00"},
            {
                "direction": "outbound",
                "sender_type": "bot",
                "text": "Salom!",
                "created_at": "2025-01-01T10:00:05",
            },
        ]
        result = build_replay(contact={"id": 5}, messages=msgs)
        assert result.summary.total_events >= 2
        assert result.summary.user_messages >= 1
        assert result.summary.bot_replies >= 1

    def test_replay_with_traces(self) -> None:
        traces = [{"price_estimate": 5000000, "area_m2": 20, "timestamp": "2025-01-01T11:00:00"}]
        result = build_replay(contact={"id": 2}, traces=traces)
        assert result.summary.price_events == 1

    def test_replay_with_handoffs(self) -> None:
        handoffs = [{"id": 10, "status": "pending", "created_at": "2025-01-01T12:00:00"}]
        result = build_replay(contact={"id": 3}, handoffs=handoffs)
        assert result.summary.handoff_events == 1

    def test_replay_with_phone(self) -> None:
        result = build_replay(contact={"id": 4, "phone": "+998901234567"})
        phone_events = [e for e in result.events if e.event_type == "phone_shared"]
        assert len(phone_events) == 1

    def test_replay_contact_id_in_result(self) -> None:
        result = build_replay(contact={"id": 99})
        assert result.contact_id == 99

    def test_replay_events_sorted(self) -> None:
        msgs = [
            {"direction": "inbound", "text": "b", "created_at": "2025-01-01T10:05:00"},
            {"direction": "inbound", "text": "a", "created_at": "2025-01-01T10:00:00"},
        ]
        result = build_replay(contact={"id": 1}, messages=msgs)
        timestamps = [e.timestamp for e in result.events if e.timestamp]
        assert timestamps == sorted(timestamps)

    def test_replay_intent_generates_extra_event(self) -> None:
        msgs = [{"direction": "inbound", "text": "narx qancha?", "created_at": "2025-01-01T10:00"}]
        result = build_replay(contact={"id": 1}, messages=msgs)
        intent_events = [e for e in result.events if e.event_type == "ai_detected_intent"]
        assert len(intent_events) >= 1

    def test_replay_objection_generates_events(self) -> None:
        msgs = [{"direction": "inbound", "text": "qimmat ekan", "created_at": "2025-01-01T10:00"}]
        result = build_replay(contact={"id": 1}, messages=msgs)
        obj_events = [e for e in result.events if e.event_type == "objection_detected"]
        assert len(obj_events) >= 1

    def test_replay_stop_generates_stop_event(self) -> None:
        msgs = [
            {"direction": "inbound", "text": "kerak emas rahmat", "created_at": "2025-01-01T10:00"}
        ]
        result = build_replay(contact={"id": 1}, messages=msgs)
        stop_events = [e for e in result.events if e.event_type == "stop_requested"]
        assert len(stop_events) >= 1


class TestClassifyMessageEvent:
    def test_inbound_is_user(self) -> None:
        evt = classify_message_event({"direction": "inbound", "text": "hi"})
        assert evt.actor == "user"
        assert evt.event_type == "user_message"

    def test_outbound_bot(self) -> None:
        evt = classify_message_event(
            {"direction": "outbound", "sender_type": "bot", "text": "hello"}
        )
        assert evt.actor == "bot"
        assert evt.event_type == "bot_reply"

    def test_operator_reply(self) -> None:
        evt = classify_message_event(
            {"direction": "outbound", "sender_type": "operator", "text": "ok"}
        )
        assert evt.actor == "operator"
        assert evt.event_type == "operator_reply"

    def test_timestamp_extracted(self) -> None:
        evt = classify_message_event(
            {"direction": "inbound", "text": "x", "created_at": "2025-01-01T10:00:00Z"}
        )
        assert evt.timestamp is not None
        assert "2025-01-01" in evt.timestamp

    def test_event_id_not_empty(self) -> None:
        evt = classify_message_event({"direction": "inbound", "text": "x"})
        assert evt.event_id != ""

    def test_icon_key_set(self) -> None:
        evt = classify_message_event({"direction": "inbound", "text": "x"})
        assert evt.icon_key == "user"

    def test_contact_id_passed(self) -> None:
        evt = classify_message_event({"direction": "inbound", "text": "x"}, contact_id=42)
        assert evt.related_contact_id == 42

    def test_preview_sanitized(self) -> None:
        evt = classify_message_event(
            {"direction": "inbound", "text": "my token sk-abcdefghijklmnop is secret"}
        )
        assert "sk-abcdefghijklmnop" not in (evt.message_preview or "")

    def test_phone_masked_in_preview(self) -> None:
        evt = classify_message_event({"direction": "inbound", "text": "raqamim +998901234567"})
        assert "+998901234567" not in (evt.message_preview or "")
        assert "****" in (evt.message_preview or "")


class TestDetectIntent:
    def test_price_intent(self) -> None:
        assert detect_intent("narx qancha") == "price"

    def test_measurement_intent(self) -> None:
        assert detect_intent("o'lchov qilish kerak") == "measurement"

    def test_catalog_intent(self) -> None:
        assert detect_intent("katalog ko'rsat") == "catalog"

    def test_order_intent(self) -> None:
        assert detect_intent("buyurtma beraman") == "order"

    def test_stop_intent(self) -> None:
        assert detect_intent("kerak emas") == "stop"

    def test_operator_intent(self) -> None:
        assert detect_intent("operator chaqiring") == "operator"

    def test_phone_intent(self) -> None:
        assert detect_intent("telefon raqamim") == "phone"

    def test_objection_price(self) -> None:
        assert detect_intent("qimmat ekan") == "objection_price"

    def test_objection_delay(self) -> None:
        assert detect_intent("keyinroq gaplashamiz") == "objection_delay"

    def test_objection_compare(self) -> None:
        assert detect_intent("raqobatchi bilan solishtiryapman") == "objection_compare"

    def test_unknown_returns_none(self) -> None:
        assert detect_intent("salom dunyo") is None

    def test_case_insensitive(self) -> None:
        assert detect_intent("NARX qancha?") == "price"


class TestSanitize:
    def test_sanitize_preview_none(self) -> None:
        assert sanitize_preview(None) is None

    def test_sanitize_preview_empty(self) -> None:
        assert sanitize_preview("") is None

    def test_sanitize_removes_token(self) -> None:
        result = sanitize_preview("token sk-abcdefghijk12345 here")
        assert "sk-abcdefghijk12345" not in (result or "")
        assert "[REDACTED]" in (result or "")

    def test_sanitize_removes_bot_token(self) -> None:
        result = sanitize_preview("bot123456:AABBCCDDEEFFgghh_1234567890")
        assert "AABBCCDDEEFFgghh" not in (result or "")

    def test_sanitize_removes_bearer(self) -> None:
        result = sanitize_preview("Bearer eyJhbGciOiJIUzI1NiJ9.test")
        assert "eyJhbGciOiJIUzI1NiJ9" not in (result or "")

    def test_sanitize_removes_db_url(self) -> None:
        result = sanitize_preview("url: postgresql://user:pass@host/db")
        assert "postgresql://" not in (result or "")

    def test_sanitize_truncates(self) -> None:
        long_text = "a" * 500
        result = sanitize_preview(long_text, max_len=100)
        assert len(result or "") <= 100

    def test_sanitize_escapes_html(self) -> None:
        result = sanitize_preview("<script>alert(1)</script>")
        assert "<script>" not in (result or "")
        assert "&lt;" in (result or "")

    def test_mask_phone_in_text(self) -> None:
        result = mask_phone_in_text("call +998901234567 please")
        assert "+998901234567" not in result
        assert "****" in result

    def test_mask_phone_short_number_kept(self) -> None:
        result = mask_phone_in_text("code 1234")
        assert "1234" in result

    def test_sanitize_metadata_none(self) -> None:
        assert sanitize_metadata(None) is None

    def test_sanitize_metadata_empty(self) -> None:
        assert sanitize_metadata({}) is None

    def test_sanitize_metadata_safe_keys(self) -> None:
        result = sanitize_metadata({"intent": "price", "area_m2": 20, "secret_key": "hidden"})
        assert "intent: price" in (result or "")
        assert "area_m2: 20" in (result or "")
        assert "hidden" not in (result or "")


class TestBuildEvents:
    def test_build_intent_event(self) -> None:
        evt = build_intent_event("narx?", "price", ts="2025-01-01T10:00")
        assert evt.event_type == "ai_detected_intent"
        assert evt.actor == "ai"
        assert evt.intent == "price"

    def test_build_price_event(self) -> None:
        evt = build_price_event(
            {"price_estimate": 5000000, "area_m2": 20, "timestamp": "2025-01-01"}
        )
        assert evt.event_type == "price_estimate"
        assert "5000000" in evt.description

    def test_build_price_event_with_design(self) -> None:
        evt = build_price_event(
            {"price_estimate": 3000000, "area_m2": 15, "design_type": "matoviy", "timestamp": ""}
        )
        assert "matoviy" in evt.description

    def test_build_objection_event(self) -> None:
        evt = build_objection_event({"objection_type": "price", "timestamp": "2025-01-01"})
        assert evt.event_type == "objection_detected"
        assert evt.severity == "warning"

    def test_build_objection_unknown_type(self) -> None:
        evt = build_objection_event({"objection_type": "unknown_x", "timestamp": ""})
        assert "unknown_x" in evt.title

    def test_build_handoff_pending(self) -> None:
        evt = build_handoff_event({"id": 5, "status": "pending", "created_at": "2025-01-01"})
        assert evt.event_type == "handoff_requested"
        assert evt.related_handoff_id == 5

    def test_build_handoff_resolved(self) -> None:
        evt = build_handoff_event({"id": 6, "status": "resolved", "created_at": "2025-01-01"})
        assert evt.event_type == "handoff_status_changed"
        assert evt.status == "resolved"

    def test_build_handoff_with_reason(self) -> None:
        evt = build_handoff_event(
            {"id": 7, "status": "pending", "reason": "urgent", "created_at": ""}
        )
        assert "urgent" in evt.description

    def test_build_phone_event(self) -> None:
        evt = build_phone_event(ts="2025-01-01T10:00", contact_id=1)
        assert evt.event_type == "phone_shared"
        assert evt.actor == "user"

    def test_build_stop_event(self) -> None:
        evt = build_stop_event(ts="2025-01-01T10:00", text="kerak emas")
        assert evt.event_type == "stop_requested"
        assert evt.severity == "warning"

    def test_build_stop_event_preview_sanitized(self) -> None:
        evt = build_stop_event(text="stop sk-secrettoken123456789")
        assert "sk-secrettoken123456789" not in (evt.message_preview or "")


class TestSortEvents:
    def test_sorts_by_timestamp(self) -> None:
        events = [
            ConversationReplayEvent(event_type="a", timestamp="2025-01-01T10:05"),
            ConversationReplayEvent(event_type="b", timestamp="2025-01-01T10:00"),
        ]
        result = sort_events_chronologically(events)
        assert result[0].event_type == "b"
        assert result[1].event_type == "a"

    def test_none_timestamps_first(self) -> None:
        events = [
            ConversationReplayEvent(event_type="a", timestamp="2025-01-01T10:00"),
            ConversationReplayEvent(event_type="b", timestamp=None),
        ]
        result = sort_events_chronologically(events)
        assert result[0].event_type == "b"

    def test_empty_list(self) -> None:
        assert sort_events_chronologically([]) == []


class TestBuildSummary:
    def test_empty_summary(self) -> None:
        s = build_summary([])
        assert s.total_events == 0
        assert s.recommended_next_action != ""

    def test_counts_correct(self) -> None:
        events = [
            ConversationReplayEvent(event_type="user_message"),
            ConversationReplayEvent(event_type="user_message"),
            ConversationReplayEvent(event_type="bot_reply"),
            ConversationReplayEvent(event_type="price_estimate"),
            ConversationReplayEvent(event_type="objection_detected"),
            ConversationReplayEvent(event_type="handoff_requested"),
            ConversationReplayEvent(event_type="stop_requested"),
        ]
        s = build_summary(events)
        assert s.total_events == 7
        assert s.user_messages == 2
        assert s.bot_replies == 1
        assert s.price_events == 1
        assert s.objections == 1
        assert s.handoff_events == 1
        assert s.stop_events == 1

    def test_first_and_last_timestamps(self) -> None:
        events = [
            ConversationReplayEvent(event_type="a", timestamp="2025-01-01T10:00"),
            ConversationReplayEvent(event_type="b", timestamp="2025-01-01T12:00"),
        ]
        s = build_summary(events)
        assert s.first_seen_at == "2025-01-01T10:00"
        assert s.last_event_at == "2025-01-01T12:00"

    def test_no_timestamps(self) -> None:
        events = [ConversationReplayEvent(event_type="a")]
        s = build_summary(events)
        assert s.first_seen_at is None
        assert s.last_event_at is None

    def test_recommended_action_stop(self) -> None:
        events = [ConversationReplayEvent(event_type="stop_requested")]
        s = build_summary(events)
        assert (
            "to'xtatdi" in s.recommended_next_action.lower()
            or "ulanmang" in s.recommended_next_action.lower()
        )

    def test_recommended_action_handoff_pending(self) -> None:
        events = [ConversationReplayEvent(event_type="handoff_requested")]
        s = build_summary(events)
        assert (
            "handoff" in s.recommended_next_action.lower()
            or "operator" in s.recommended_next_action.lower()
        )

    def test_recommended_action_objection(self) -> None:
        events = [ConversationReplayEvent(event_type="objection_detected")]
        s = build_summary(events)
        assert (
            "e'tiroz" in s.recommended_next_action.lower()
            or "taklif" in s.recommended_next_action.lower()
        )

    def test_recommended_action_price(self) -> None:
        events = [ConversationReplayEvent(event_type="price_estimate")]
        s = build_summary(events)
        assert (
            "narx" in s.recommended_next_action.lower()
            or "o'lchov" in s.recommended_next_action.lower()
        )

    def test_recommended_action_unanswered(self) -> None:
        events = [
            ConversationReplayEvent(event_type="user_message", timestamp="2025-01-01T10:05"),
            ConversationReplayEvent(event_type="bot_reply", timestamp="2025-01-01T10:00"),
        ]
        s = build_summary(events)
        assert "javob" in s.recommended_next_action.lower()

    def test_operator_reply_counted_as_bot(self) -> None:
        events = [ConversationReplayEvent(event_type="operator_reply")]
        s = build_summary(events)
        assert s.bot_replies == 1


class TestValidEventTypes:
    def test_all_icon_map_keys_valid(self) -> None:
        for key in ICON_MAP:
            assert key in VALID_EVENT_TYPES

    def test_14_event_types(self) -> None:
        assert len(VALID_EVENT_TYPES) == 14


class TestMissingData:
    def test_missing_timestamps_handled(self) -> None:
        msgs = [{"direction": "inbound", "text": "hi"}]
        result = build_replay(contact={"id": 1}, messages=msgs)
        assert result.summary.total_events >= 1

    def test_missing_text_handled(self) -> None:
        msgs = [{"direction": "inbound"}]
        result = build_replay(contact={"id": 1}, messages=msgs)
        assert result.summary.total_events >= 1

    def test_unknown_sender_type(self) -> None:
        evt = classify_message_event(
            {"direction": "outbound", "sender_type": "unknown", "text": "x"}
        )
        assert evt.actor == "bot"

    def test_empty_contact(self) -> None:
        result = build_replay(contact={})
        assert result.contact_id == 0
        assert result.events == []
