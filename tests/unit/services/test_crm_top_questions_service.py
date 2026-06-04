"""Unit tests for crm_top_questions_service — deterministic, offline.

Pure normalize/group functions are tested directly; collect_top_questions is
tested with an in-memory fake session. No DB/Redis/Telegram/OpenAI.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core.services.crm_top_questions_service import (
    TOP_QUESTIONS_SOURCE,
    collect_top_questions,
    group_top_questions,
    normalize_question,
)

_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _t(minutes_ago: int) -> datetime:
    return _NOW - timedelta(minutes=minutes_ago)


# ── normalization (deterministic, conservative) ──────────────────────────────


class TestNormalize:
    def test_lowercase(self):
        assert normalize_question("NARX Qancha") == "narx qancha"

    def test_trim_and_collapse_whitespace(self):
        assert normalize_question("  narx    qancha  ") == "narx qancha"

    def test_strip_punctuation(self):
        assert normalize_question("Narx qancha?!.") == "narx qancha"

    def test_apostrophes_folded(self):
        # curly / modifier-letter / backtick apostrophes all fold to one ASCII '
        assert normalize_question("o‘lcham") == normalize_question("o'lcham")
        assert normalize_question("oʻlcham") == "o'lcham"
        assert normalize_question("o`lcham") == "o'lcham"

    def test_emoji_and_noise_removed(self):
        assert normalize_question("Narx qancha 😀🔥") == "narx qancha"

    def test_digits_kept(self):
        assert normalize_question("3 xona narxi") == "3 xona narxi"

    def test_empty_and_none(self):
        assert normalize_question("") == ""
        assert normalize_question(None) == ""
        assert normalize_question("???") == ""  # punctuation-only → blank

    def test_does_not_overnormalize_words(self):
        # no stemming / stopword removal — morphology preserved
        assert normalize_question("narxlari qancha bo'ladi") == "narxlari qancha bo'ladi"


# ── pure grouping ────────────────────────────────────────────────────────────


def _row(text, *, mins, reason="ai_fallback", severity="medium", status="new"):
    return {
        "text": text,
        "reason": reason,
        "severity": severity,
        "status": status,
        "created_at": _t(mins),
    }


class TestGroupTopQuestions:
    def test_groups_same_normalized_text(self):
        rows = [
            _row("Narx qancha?", mins=10),
            _row("narx   qancha", mins=5),
            _row("NARX QANCHA!", mins=1),
        ]
        out = group_top_questions(rows)
        assert len(out) == 1
        assert out[0]["normalized"] == "narx qancha"
        assert out[0]["count"] == 3

    def test_empty_source_returns_empty(self):
        assert group_top_questions([]) == []

    def test_blank_normalizing_rows_skipped(self):
        out = group_top_questions([_row("???", mins=1), _row("😀", mins=2)])
        assert out == []

    def test_sort_by_count_then_last_seen(self):
        rows = [
            _row("narx qancha", mins=50),  # group A
            _row("narx qancha", mins=40),  # A count=2
            _row("katalog bormi", mins=5),  # group B count=1, newer
            _row("o'lcham qancha", mins=60),  # group C count=1, older
        ]
        out = group_top_questions(rows)
        assert [g["normalized"] for g in out] == [
            "narx qancha",  # highest count first
            "katalog bormi",  # tie count=1 → newer last_seen first
            "o'lcham qancha",
        ]

    def test_tie_break_normalized_asc(self):
        # same count, same last_seen → normalized ascending for determinism
        rows = [_row("bbb", mins=10), _row("aaa", mins=10)]
        out = group_top_questions(rows)
        assert [g["normalized"] for g in out] == ["aaa", "bbb"]

    def test_limit_default_ten(self):
        rows = [_row(f"savol raqam {i}", mins=i) for i in range(15)]
        out = group_top_questions(rows)
        assert len(out) == 10

    def test_limit_custom(self):
        rows = [_row(f"savol {i}", mins=i) for i in range(8)]
        assert len(group_top_questions(rows, limit=3)) == 3

    def test_representative_is_most_recent(self):
        rows = [
            _row("narx qancha", mins=30, reason="old", severity="low", status="reviewed"),
            _row("Narx qancha?", mins=2, reason="new", severity="high", status="new"),
        ]
        g = group_top_questions(rows)[0]
        assert g["sample"] == "Narx qancha?"  # most recent original preview
        assert g["reason"] == "new"
        assert g["severity"] == "high"
        assert g["status"] == "new"
        assert g["last_seen"] == _t(2).isoformat()

    def test_count_and_last_seen_shape(self):
        g = group_top_questions([_row("narx qancha", mins=5)])[0]
        assert g["count"] == 1
        assert g["last_seen"] == _t(5).isoformat()
        assert set(g) == {
            "normalized",
            "sample",
            "count",
            "last_seen",
            "reason",
            "severity",
            "status",
        }


# ── collect_top_questions with an in-memory fake session ──────────────────────


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed = 0

    async def execute(self, *_a, **_k):
        self.executed += 1
        return _Result(self._rows)


class TestCollectTopQuestions:
    async def test_builds_grouped_items(self):
        rows = [
            SimpleNamespace(
                original_text_preview="Narx qancha?",
                reason="price",
                severity="medium",
                status="new",
                created_at=_t(10),
            ),
            SimpleNamespace(
                original_text_preview="narx qancha",
                reason="price",
                severity="medium",
                status="new",
                created_at=_t(5),
            ),
            SimpleNamespace(
                original_text_preview="Katalog bormi?",
                reason="catalog",
                severity="low",
                status="new",
                created_at=_t(3),
            ),
        ]
        out = await collect_top_questions(_FakeSession(rows), _t(60), _NOW)
        assert [g["normalized"] for g in out] == ["narx qancha", "katalog bormi"]
        assert out[0]["count"] == 2

    async def test_no_data_returns_empty(self):
        out = await collect_top_questions(_FakeSession([]), _t(60), _NOW)
        assert out == []


def test_source_constant():
    assert TOP_QUESTIONS_SOURCE == "agent_unknown_questions"
