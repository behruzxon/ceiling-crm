"""Unit tests for the real missed-leads loader — deterministic, offline.

Pure detection/classification functions are tested directly; collect_missed_items
is tested with an in-memory fake session. No DB/Redis/network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core.services.crm_daily_summary_service import Period
from core.services.crm_missed_leads_loader_service import (
    classify_wait_severity,
    collect_missed_items,
    compute_missed_contacts,
)

_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _t(minutes_ago: int) -> datetime:
    return _NOW - timedelta(minutes=minutes_ago)


# ── wait-based severity (deterministic, reliable) ────────────────────────────


class TestClassifyWaitSeverity:
    def test_tiers(self):
        assert classify_wait_severity(5) == "low"
        assert classify_wait_severity(14) == "low"
        assert classify_wait_severity(15) == "medium"
        assert classify_wait_severity(59) == "medium"
        assert classify_wait_severity(60) == "high"
        assert classify_wait_severity(179) == "high"
        assert classify_wait_severity(180) == "critical"


# ── deterministic missed detection ───────────────────────────────────────────


class TestComputeMissedContacts:
    def test_inbound_only_is_missed(self):
        rows = [(1, _t(30), "inbound")]
        assert compute_missed_contacts(rows, _NOW) == {1: 30}

    def test_inbound_then_outbound_is_not_missed(self):
        rows = [(1, _t(30), "inbound"), (1, _t(10), "outbound")]
        assert compute_missed_contacts(rows, _NOW) == {}

    def test_outbound_then_inbound_is_missed(self):
        # an earlier outbound is NOT a reply to the later inbound
        rows = [(1, _t(40), "outbound"), (1, _t(20), "inbound")]
        assert compute_missed_contacts(rows, _NOW) == {1: 20}

    def test_latest_message_decides(self):
        rows = [
            (1, _t(60), "inbound"),
            (1, _t(50), "outbound"),
            (1, _t(5), "inbound"),  # latest is inbound → missed, wait=5
        ]
        assert compute_missed_contacts(rows, _NOW) == {1: 5}

    def test_multiple_contacts_mixed(self):
        rows = [
            (1, _t(30), "inbound"),  # missed
            (2, _t(20), "inbound"),
            (2, _t(5), "outbound"),  # answered → not missed
            (3, _t(200), "inbound"),  # missed (old)
        ]
        assert compute_missed_contacts(rows, _NOW) == {1: 30, 3: 200}

    def test_agent_trace_ignored(self):
        # an internal agent_trace after the inbound must not mark it answered
        rows = [(1, _t(30), "inbound"), (1, _t(10), "agent_trace")]
        assert compute_missed_contacts(rows, _NOW) == {1: 30}

    def test_empty(self):
        assert compute_missed_contacts([], _NOW) == {}


# ── collect_missed_items with an in-memory fake session ──────────────────────


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, *, rows=None, scalar_list=None):
        self._rows = rows
        self._scalar_list = scalar_list

    def all(self):
        return self._rows

    def scalars(self):
        return _Scalars(self._scalar_list)


class _FakeSession:
    def __init__(self, results):
        self._it = iter(results)

    async def execute(self, *_a, **_k):
        return next(self._it)


def _period() -> Period:
    return Period(start=_NOW - timedelta(days=7), end=_NOW, timezone="Asia/Tashkent")


class TestCollectMissedItems:
    async def test_builds_real_items_sorted_by_wait(self):
        msg_rows = [
            SimpleNamespace(contact_id=1, created_at=_t(30), direction="inbound"),
            SimpleNamespace(contact_id=2, created_at=_t(200), direction="inbound"),
            SimpleNamespace(contact_id=3, created_at=_t(5), direction="inbound"),
            SimpleNamespace(contact_id=3, created_at=_t(2), direction="outbound"),  # answered
        ]
        contacts = [
            SimpleNamespace(
                id=1,
                first_name="Ali",
                last_name="Valiev",
                username=None,
                phone=None,
                lead_score=20,
                temperature=None,
            ),
            SimpleNamespace(
                id=2,
                first_name=None,
                last_name=None,
                username="vali",
                phone="+998901234567",
                lead_score=50,
                temperature="warm",
            ),
        ]
        session = _FakeSession([_Result(rows=msg_rows), _Result(scalar_list=contacts)])
        items = await collect_missed_items(session, _period())
        assert [i.contact_id for i in items] == [2, 1]  # 200min before 30min
        assert items[0].severity == "critical"  # 200 min
        assert items[1].severity == "medium"  # 30 min
        assert items[0].display_name == "@vali"
        assert items[1].display_name == "Ali Valiev"
        assert all(i.reason == "unanswered" for i in items)

    async def test_no_missed_returns_empty(self):
        msg_rows = [
            SimpleNamespace(contact_id=1, created_at=_t(30), direction="inbound"),
            SimpleNamespace(contact_id=1, created_at=_t(5), direction="outbound"),
        ]
        session = _FakeSession([_Result(rows=msg_rows)])  # no second query when empty
        items = await collect_missed_items(session, _period())
        assert items == []
