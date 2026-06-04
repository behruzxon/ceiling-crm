"""Unit tests for CRMAnalyticsSummaryService — deterministic, offline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core.services.crm_analytics_summary_service import (
    TrendRaw,
    build_analytics_summary,
    collect_trend,
    date_skeleton,
    shape_analytics_summary,
)
from core.services.crm_daily_summary_service import Period

_NOW = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)


def _period(days: int = 6) -> Period:
    end = datetime(2026, 6, 4, tzinfo=UTC)
    return Period(start=end - timedelta(days=days), end=end, timezone="Asia/Tashkent")


class TestDateSkeleton:
    def test_inclusive_day_range(self):
        dates = date_skeleton(_period(6))
        assert len(dates) == 7
        assert dates[0] == "2026-05-29"
        assert dates[-1] == "2026-06-04"


class TestShapeAnalyticsSummary:
    def test_empty_yields_zero_totals_and_full_skeleton(self):
        out = shape_analytics_summary("7d", _period(6), TrendRaw())
        assert len(out["trend"]) == 7
        assert out["totals"] == {
            "messages": 0,
            "incoming": 0,
            "outgoing": 0,
            "new_contacts": 0,
            "unknown_questions": 0,
        }
        assert all(d["messages"] == 0 for d in out["trend"])
        assert out["handoffs"] == {"open": 0, "assigned": 0, "resolved": 0}
        assert out["data_quality"] == {
            "intent_reliable": False,
            "source_reliable": False,
            "temperature_reliable": False,
        }

    def test_per_day_split_and_totals(self):
        raw = TrendRaw(
            messages_in={"2026-06-04": 5},
            messages_out={"2026-06-04": 3, "2026-06-03": 1},
            new_contacts={"2026-06-04": 2},
            unknown={"2026-06-03": 4},
            open_handoffs=2,
            assigned_handoffs=1,
            resolved_handoffs=7,
        )
        out = shape_analytics_summary("7d", _period(6), raw)
        last = out["trend"][-1]  # 2026-06-04
        assert last == {
            "date": "2026-06-04",
            "messages": 8,
            "incoming": 5,
            "outgoing": 3,
            "new_contacts": 2,
            "unknown_questions": 0,
        }
        assert out["totals"]["messages"] == 9  # 8 + 1 (06-03 outgoing)
        assert out["totals"]["incoming"] == 5
        assert out["totals"]["unknown_questions"] == 4
        assert out["handoffs"] == {"open": 2, "assigned": 1, "resolved": 7}


# ── collect_trend + orchestrator with fakes ──────────────────────────────────


class _Result:
    def __init__(self, *, rows=None, one=None):
        self._rows = rows
        self._one = one

    def all(self):
        return self._rows

    def one(self):
        return self._one


class _FakeSession:
    def __init__(self, results):
        self._it = iter(results)

    async def execute(self, *_a, **_k):
        return next(self._it)


class TestCollectTrend:
    async def test_maps_rows(self):
        d = datetime(2026, 6, 4).date()
        results = [
            _Result(
                rows=[(d, "inbound", 5), (d, "outbound", 3), (d, "agent_trace", 9)]
            ),  # messages
            _Result(rows=[(d, 2)]),  # contacts
            _Result(rows=[(d, 4)]),  # unknown
            _Result(one=SimpleNamespace(open=1, assigned=0, resolved=2)),  # handoff
        ]
        raw = await collect_trend(_FakeSession(results), _period(6))
        assert raw.messages_in == {"2026-06-04": 5}
        assert raw.messages_out == {"2026-06-04": 3}  # agent_trace ignored
        assert raw.new_contacts == {"2026-06-04": 2}
        assert raw.unknown == {"2026-06-04": 4}
        assert (raw.open_handoffs, raw.resolved_handoffs) == (1, 2)


class TestBuildAnalyticsSummary:
    async def test_orchestrates(self, monkeypatch):
        async def _fake_collect(session, period):
            return TrendRaw(messages_in={"2026-06-04": 3})

        monkeypatch.setattr(
            "core.services.crm_analytics_summary_service.collect_trend", _fake_collect
        )
        out = await build_analytics_summary(object(), range_="7d", now=_NOW)
        assert out["range"] == "7d"
        assert out["totals"]["incoming"] == 3
        assert out["period"]["timezone"] == "Asia/Tashkent"
