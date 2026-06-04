"""Unit tests for CRMDailySummaryService — deterministic, offline.

Pure functions (validate_range, resolve_period, shape_summary, hourly) are
tested directly; collect_raw_counts is tested with an in-memory fake session.
No DB/Redis/Telegram/OpenAI.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.services.crm_daily_summary_service import (
    Period,
    RawCounts,
    build_daily_summary,
    collect_raw_counts,
    empty_hourly,
    resolve_period,
    shape_summary,
    validate_range,
)

_NOW = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)  # fixed for determinism


# ── range validation ─────────────────────────────────────────────────────────


class TestValidateRange:
    @pytest.mark.parametrize("r", ["today", "7d", "30d"])
    def test_valid(self, r):
        assert validate_range(r) == r

    @pytest.mark.parametrize("r", ["bogus", "1d", "", "TODAY", "day"])
    def test_invalid_raises(self, r):
        with pytest.raises(ValueError, match="invalid range"):
            validate_range(r)


# ── period resolution ────────────────────────────────────────────────────────


class TestResolvePeriod:
    def test_today_starts_at_local_midnight(self):
        p = resolve_period("today", _NOW)
        assert p.timezone == "Asia/Tashkent"
        assert p.start.utcoffset() == timedelta(hours=5)  # UTC+5 (ZoneInfo or fallback)
        assert (p.start.hour, p.start.minute, p.start.second) == (0, 0, 0)
        assert p.start <= p.end
        assert p.end - p.start < timedelta(days=1)

    def test_7d_window_is_seven_days(self):
        p = resolve_period("7d", _NOW)
        assert p.end - p.start == timedelta(days=7)

    def test_30d_window_is_thirty_days(self):
        p = resolve_period("30d", _NOW)
        assert p.end - p.start == timedelta(days=30)


# ── pure shaping ─────────────────────────────────────────────────────────────


def _period() -> Period:
    return Period(start=_NOW, end=_NOW, timezone="Asia/Tashkent")


class TestShapeEmptyDay:
    def test_all_zeros_and_unavailable_marked(self):
        out = shape_summary("today", _period(), RawCounts())
        k = out["kpis"]
        assert k["total_messages"] == 0
        assert k["incoming_messages"] == 0
        assert k["outgoing_messages"] == 0
        assert k["new_contacts"] == 0
        assert k["operator_requests"] == 0
        assert k["missed_leads"] == 0
        assert k["unknown_questions"] == 0
        assert k["open_handoffs"] == 0
        assert k["assigned_handoffs"] == 0
        assert k["resolved_handoffs"] == 0
        # unreliable fields are null, NOT a fabricated 0
        assert k["price_requests"] is None
        assert k["catalog_requests"] is None
        assert k["hot_leads"] is None
        assert k["warm_leads"] is None
        assert k["cold_leads"] is None
        assert out["top_questions"] == []
        assert out["unknown_questions"] == []
        assert out["warnings"] == []

    def test_hourly_has_24_zero_buckets(self):
        out = shape_summary("today", _period(), RawCounts())
        assert len(out["hourly_activity"]) == 24
        assert [b["hour"] for b in out["hourly_activity"]] == list(range(24))
        assert all(b["messages"] == 0 and b["new_contacts"] == 0 for b in out["hourly_activity"])

    def test_data_quality_flags_false(self):
        dq = shape_summary("today", _period(), RawCounts())["data_quality"]
        assert dq == {
            "intent_reliable": False,
            "source_reliable": False,
            "temperature_reliable": False,
            "top_questions_reliable": True,
            "top_questions_source": "agent_unknown_questions",
        }


class TestShapeWithData:
    def test_messages_split_and_total(self):
        out = shape_summary("today", _period(), RawCounts(incoming_messages=5, outgoing_messages=3))
        assert out["kpis"]["incoming_messages"] == 5
        assert out["kpis"]["outgoing_messages"] == 3
        assert out["kpis"]["total_messages"] == 8

    def test_hourly_buckets_filled(self):
        raw = RawCounts(hourly_messages={9: 4, 18: 2}, hourly_new_contacts={9: 1})
        buckets = shape_summary("today", _period(), raw)["hourly_activity"]
        assert buckets[9] == {"hour": 9, "messages": 4, "new_contacts": 1}
        assert buckets[18] == {"hour": 18, "messages": 2, "new_contacts": 0}
        assert buckets[0] == {"hour": 0, "messages": 0, "new_contacts": 0}

    def test_handoff_status_counts(self):
        out = shape_summary(
            "today", _period(), RawCounts(open_handoffs=2, assigned_handoffs=1, resolved_handoffs=4)
        )
        assert out["kpis"]["open_handoffs"] == 2
        assert out["kpis"]["assigned_handoffs"] == 1
        assert out["kpis"]["resolved_handoffs"] == 4

    def test_unknown_count_and_list_passthrough(self):
        items = [{"id": 1, "text": "narx?", "reason": "ai_fallback", "severity": "low"}]
        out = shape_summary("today", _period(), RawCounts(unknown_questions=7, unknown_items=items))
        assert out["kpis"]["unknown_questions"] == 7
        assert out["unknown_questions"] == items

    def test_warnings_only_from_real_signals(self):
        raw = RawCounts(open_handoffs=3, missed_leads=2, unknown_questions=1)
        types = {w["type"] for w in shape_summary("today", _period(), raw)["warnings"]}
        assert types == {"needs_operator", "missed", "unknown"}

    def test_no_warnings_when_quiet(self):
        assert shape_summary("today", _period(), RawCounts())["warnings"] == []


def test_empty_hourly_is_24_buckets():
    buckets = empty_hourly()
    assert len(buckets) == 24
    assert buckets[23] == {"hour": 23, "messages": 0, "new_contacts": 0}


# ── collect_raw_counts with an in-memory fake session ────────────────────────


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, *, rows=None, scalar=None, one=None, scalar_list=None):
        self._rows = rows
        self._scalar = scalar
        self._one = one
        self._scalar_list = scalar_list

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar

    def one(self):
        return self._one

    def scalars(self):
        return _Scalars(self._scalar_list)


class _FakeSession:
    """Returns canned results in the exact order collect_raw_counts queries."""

    def __init__(self, results):
        self._it = iter(results)

    async def execute(self, *_args, **_kwargs):
        return next(self._it)


class TestCollectRawCounts:
    async def test_maps_db_rows_into_raw_counts(self):
        uq_row = SimpleNamespace(
            id=1,
            original_text_preview="narx qancha?",
            reason="ai_fallback",
            severity="low",
            created_at=_NOW,
        )
        results = [
            _Result(rows=[("inbound", 5), ("outbound", 3), ("agent_trace", 9)]),  # directions
            _Result(scalar=4),  # new_contacts
            _Result(scalar=2),  # operator_requests
            _Result(one=SimpleNamespace(open=2, assigned=1, resolved=3)),  # handoff state
            _Result(scalar_list=[1, 2, 3]),  # inbound contact ids
            _Result(scalar_list=[2]),  # replied contact ids
            _Result(scalar=7),  # unknown count
            _Result(rows=[uq_row]),  # unknown list
            _Result(rows=[(9, 4), (18, 2)]),  # message hours
            _Result(rows=[(9, 1)]),  # contact hours
        ]
        raw = await collect_raw_counts(_FakeSession(results), _period())
        assert raw.incoming_messages == 5
        assert raw.outgoing_messages == 3  # agent_trace ignored for in/out
        assert raw.new_contacts == 4
        assert raw.operator_requests == 2
        assert (raw.open_handoffs, raw.assigned_handoffs, raw.resolved_handoffs) == (2, 1, 3)
        assert raw.missed_leads == 2  # {1,2,3} inbound minus {2} replied
        assert raw.unknown_questions == 7
        assert raw.unknown_items[0]["text"] == "narx qancha?"
        assert raw.hourly_messages == {9: 4, 18: 2}
        assert raw.hourly_new_contacts == {9: 1}

    async def test_empty_db_yields_all_zeros(self):
        results = [
            _Result(rows=[]),  # directions
            _Result(scalar=0),  # new_contacts
            _Result(scalar=0),  # operator_requests
            _Result(one=SimpleNamespace(open=0, assigned=0, resolved=0)),
            _Result(scalar_list=[]),  # inbound
            _Result(scalar_list=[]),  # replied
            _Result(scalar=0),  # unknown count
            _Result(rows=[]),  # unknown list
            _Result(rows=[]),  # msg hours
            _Result(rows=[]),  # contact hours
        ]
        raw = await collect_raw_counts(_FakeSession(results), _period())
        out = shape_summary("today", _period(), raw)
        assert out["kpis"]["total_messages"] == 0
        assert out["kpis"]["missed_leads"] == 0
        assert out["unknown_questions"] == []


# ── orchestrator (period + shape) without DB ─────────────────────────────────


class TestBuildDailySummary:
    async def test_orchestrates_period_and_shape(self, monkeypatch):
        captured = {}

        async def _fake_collect(session, period):
            captured["period"] = period
            return RawCounts(incoming_messages=2, outgoing_messages=1)

        async def _fake_top_questions(session, start, end, limit=10):
            captured["tq_window"] = (start, end)
            return []

        monkeypatch.setattr(
            "core.services.crm_daily_summary_service.collect_raw_counts", _fake_collect
        )
        monkeypatch.setattr(
            "core.services.crm_daily_summary_service.collect_top_questions", _fake_top_questions
        )
        out = await build_daily_summary(object(), range_="7d", now=_NOW)
        assert out["range"] == "7d"
        assert out["kpis"]["total_messages"] == 3
        assert out["top_questions"] == []
        assert out["period"]["timezone"] == "Asia/Tashkent"
        assert captured["period"].end - captured["period"].start == timedelta(days=7)

    async def test_invalid_range_raises(self):
        with pytest.raises(ValueError, match="invalid range"):
            await build_daily_summary(object(), range_="bogus", now=_NOW)
