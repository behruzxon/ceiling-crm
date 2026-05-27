"""Tests for price estimate history service — Step 7."""

from __future__ import annotations

from core.schemas.crm_price_estimate_history import (
    PriceEstimateHistoryItem,
    PriceEstimateHistoryResult,
    PriceEstimateHistorySummary,
)
from core.services.crm_price_estimate_history_service import (
    DESIGN_TITLES,
    TAXMINIY_WARNING,
    build_history,
    build_summary,
    extract_from_ai_trace,
    extract_from_memory_payload,
    extract_from_replay_event,
    format_uzs,
    sanitize_metadata,
    sanitize_preview,
)


class TestBuildHistory:
    def test_empty_history_safe(self) -> None:
        result = build_history(contact={"id": 1})
        assert isinstance(result, PriceEstimateHistoryResult)
        assert result.contact_id == 1
        assert result.items == []
        assert result.summary.total_estimates == 0

    def test_history_from_traces(self) -> None:
        traces = [
            {
                "price_estimate": 2000000,
                "area_m2": 20,
                "design_type": "gulli",
                "timestamp": "2025-01-01T10:00",
            }
        ]
        result = build_history(contact={"id": 2}, traces=traces)
        assert result.summary.total_estimates == 1
        assert result.items[0].total_uzs == 2000000

    def test_history_from_contact_metadata(self) -> None:
        contact = {
            "id": 3,
            "metadata": {
                "last_price_estimate": 1600000,
                "area_m2": 20,
                "design_type": "adnatonniy",
            },
        }
        result = build_history(contact=contact)
        assert result.summary.total_estimates == 1

    def test_history_from_replay_events(self) -> None:
        events = [
            {
                "event_type": "price_estimate",
                "timestamp": "2025-01-01T10:00",
                "description": "Taxminiy narx hisoblandi: 2000000 UZS (20 m²)",
                "metadata_summary": "area_m2: 20 | design_type: gulli",
            }
        ]
        result = build_history(contact={"id": 4}, replay_events=events)
        assert result.summary.total_estimates == 1

    def test_dedup_same_source_and_index(self) -> None:
        traces = [
            {"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-01T10:00"},
        ]
        result = build_history(
            contact={
                "id": 5,
                "metadata": {
                    "last_price_estimate": 2000000,
                    "area_m2": 20,
                    "design_type": "",
                    "timestamp": "2025-01-01T10:00",
                    "last_price_source": "ai_trace",
                },
            },
            traces=traces,
        )
        assert result.summary.total_estimates >= 1

    def test_sorted_by_timestamp(self) -> None:
        traces = [
            {"price_estimate": 3000000, "area_m2": 30, "timestamp": "2025-01-01T12:00"},
            {"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-01T10:00"},
        ]
        result = build_history(contact={"id": 6}, traces=traces)
        timestamps = [i.timestamp for i in result.items if i.timestamp]
        assert timestamps == sorted(timestamps)

    def test_handoff_after_estimate(self) -> None:
        traces = [{"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-01T10:00"}]
        msgs = [{"text": "operator chaqiring", "direction": "inbound"}]
        result = build_history(contact={"id": 7}, traces=traces, messages=msgs)
        assert result.items[0].handoff_after_estimate is True

    def test_contact_id_in_result(self) -> None:
        result = build_history(contact={"id": 99})
        assert result.contact_id == 99


class TestExtractFromAiTrace:
    def test_extracts_area(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "area_m2": 20})
        assert item is not None
        assert item.area_m2 == 20.0

    def test_extracts_design_key(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "design_type": "gulli"})
        assert item is not None
        assert item.design_key == "gulli"

    def test_extracts_design_title(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "design_type": "gulli"})
        assert item is not None
        assert item.design_title == "Gulli"

    def test_extracts_rate(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "area_m2": 20})
        assert item is not None
        assert item.rate_uzs_per_m2 == 100000

    def test_extracts_total(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2600000, "area_m2": 20})
        assert item is not None
        assert item.total_uzs == 2600000

    def test_marks_is_estimate(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 1000000})
        assert item is not None
        assert item.is_estimate is True

    def test_includes_taxminiy_warning(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 1000000})
        assert item is not None
        assert "taxminiy" in item.warning.lower() or "Taxminiy" in item.warning

    def test_none_when_no_estimate(self) -> None:
        item = extract_from_ai_trace({"area_m2": 20})
        assert item is None

    def test_handles_string_area(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "area_m2": "20"})
        assert item is not None
        assert item.area_m2 == 20.0

    def test_handles_invalid_area(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "area_m2": "invalid"})
        assert item is not None
        assert item.area_m2 == 0.0

    def test_source_ai_trace(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 1000000})
        assert item is not None
        assert item.source == "ai_trace"

    def test_contact_id_passed(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 1000000}, contact_id=42)
        assert item is not None
        assert item.contact_id == 42


class TestExtractFromReplayEvent:
    def test_non_price_event_returns_none(self) -> None:
        item = extract_from_replay_event({"event_type": "user_message"})
        assert item is None

    def test_price_event_returns_item(self) -> None:
        item = extract_from_replay_event(
            {"event_type": "price_estimate", "timestamp": "2025-01-01"}
        )
        assert item is not None
        assert item.source == "replay"

    def test_extracts_area_from_metadata(self) -> None:
        item = extract_from_replay_event(
            {
                "event_type": "price_estimate",
                "description": "Narx hisoblandi",
                "metadata_summary": "area_m2: 25 | design_type: hi-tech",
            }
        )
        assert item is not None
        assert item.area_m2 == 25.0
        assert item.design_key == "hi-tech"


class TestExtractFromMemoryPayload:
    def test_extracts_total(self) -> None:
        item = extract_from_memory_payload(
            {"last_price_total": 2400000, "last_price_area_m2": 20, "last_price_design": "gulli"}
        )
        assert item is not None
        assert item.total_uzs == 2400000

    def test_none_when_no_total(self) -> None:
        item = extract_from_memory_payload({"last_price_area_m2": 20})
        assert item is None

    def test_source_from_payload(self) -> None:
        item = extract_from_memory_payload(
            {"last_price_total": 1000000, "last_price_source": "price_calculator"}
        )
        assert item is not None
        assert item.source == "price_calculator"

    def test_is_estimate_default(self) -> None:
        item = extract_from_memory_payload({"last_price_total": 1000000})
        assert item is not None
        assert item.is_estimate is True


class TestBuildSummary:
    def test_empty_summary(self) -> None:
        s = build_summary([])
        assert isinstance(s, PriceEstimateHistorySummary)
        assert s.total_estimates == 0

    def test_total_count(self) -> None:
        items = [
            PriceEstimateHistoryItem(total_uzs=1000000),
            PriceEstimateHistoryItem(total_uzs=2000000),
        ]
        s = build_summary(items)
        assert s.total_estimates == 2

    def test_latest_total(self) -> None:
        items = [
            PriceEstimateHistoryItem(total_uzs=1000000, timestamp="2025-01-01T10:00"),
            PriceEstimateHistoryItem(total_uzs=2000000, timestamp="2025-01-01T12:00"),
        ]
        s = build_summary(items)
        assert s.latest_total_uzs == 2000000

    def test_min_max(self) -> None:
        items = [
            PriceEstimateHistoryItem(total_uzs=1600000),
            PriceEstimateHistoryItem(total_uzs=2800000),
        ]
        s = build_summary(items)
        assert s.min_total_uzs == 1600000
        assert s.max_total_uzs == 2800000

    def test_most_requested_design(self) -> None:
        items = [
            PriceEstimateHistoryItem(design_key="gulli"),
            PriceEstimateHistoryItem(design_key="gulli"),
            PriceEstimateHistoryItem(design_key="mramor"),
        ]
        s = build_summary(items)
        assert s.most_requested_design == "gulli"

    def test_total_area(self) -> None:
        items = [
            PriceEstimateHistoryItem(area_m2=20.0),
            PriceEstimateHistoryItem(area_m2=30.0),
        ]
        s = build_summary(items)
        assert s.total_area_m2 == 50.0

    def test_handoff_count(self) -> None:
        items = [
            PriceEstimateHistoryItem(handoff_after_estimate=True),
            PriceEstimateHistoryItem(handoff_after_estimate=False),
        ]
        s = build_summary(items)
        assert s.handoff_after_estimate_count == 1

    def test_has_recent_estimate(self) -> None:
        items = [PriceEstimateHistoryItem(timestamp="2025-01-01T10:00")]
        s = build_summary(items)
        assert s.has_recent_estimate is True

    def test_no_recent_when_no_timestamps(self) -> None:
        items = [PriceEstimateHistoryItem()]
        s = build_summary(items)
        assert s.has_recent_estimate is False


class TestSanitize:
    def test_sanitize_token(self) -> None:
        result = sanitize_preview("key sk-abcdefghijk12345 here")
        assert "sk-abcdefghijk12345" not in (result or "")
        assert "[REDACTED]" in (result or "")

    def test_sanitize_db_url(self) -> None:
        result = sanitize_preview("postgresql://user:pass@host/db")
        assert "postgresql://" not in (result or "")

    def test_truncate_preview(self) -> None:
        result = sanitize_preview("x" * 500, max_len=100)
        assert len(result or "") <= 100

    def test_sanitize_preview_none(self) -> None:
        assert sanitize_preview(None) is None

    def test_sanitize_metadata_none(self) -> None:
        assert sanitize_metadata(None) is None

    def test_sanitize_metadata_safe_keys(self) -> None:
        result = sanitize_metadata({"area_m2": 20, "secret": "hidden"})
        assert "area_m2: 20" in (result or "")
        assert "hidden" not in (result or "")

    def test_sanitize_metadata_empty(self) -> None:
        assert sanitize_metadata({}) is None

    def test_no_raw_json(self) -> None:
        result = sanitize_metadata({"area_m2": 20, "raw_prompt": "text"})
        assert "raw_prompt" not in (result or "")


class TestFormatUzs:
    def test_format_simple(self) -> None:
        assert format_uzs(1000000) == "1 000 000"

    def test_format_zero(self) -> None:
        assert format_uzs(0) == "0"

    def test_format_small(self) -> None:
        assert format_uzs(500) == "500"


class TestDesignTitles:
    def test_gulli(self) -> None:
        assert DESIGN_TITLES["gulli"] == "Gulli"

    def test_adnatonniy(self) -> None:
        assert "Adnatonniy" in DESIGN_TITLES["adnatonniy"]

    def test_hi_tech(self) -> None:
        assert DESIGN_TITLES["hi-tech"] == "Hi-tech"


class TestInvalidData:
    def test_invalid_metadata_safe(self) -> None:
        result = build_history(contact={"id": 1, "metadata": {"unrelated": True}})
        assert result.items == []

    def test_unknown_source_safe(self) -> None:
        item = extract_from_memory_payload(
            {"last_price_total": 1000000, "last_price_source": "unknown_x"}
        )
        assert item is not None
        assert item.source == "unknown_x"

    def test_zero_area_no_rate_error(self) -> None:
        item = extract_from_ai_trace({"price_estimate": 2000000, "area_m2": 0})
        assert item is not None
        assert item.rate_uzs_per_m2 == 0

    def test_taxminiy_warning_present(self) -> None:
        assert "taxminiy" in TAXMINIY_WARNING.lower() or "Taxminiy" in TAXMINIY_WARNING
