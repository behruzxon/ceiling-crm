"""Step 11 — Operator daily digest service unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.schemas.crm_operator_digest import (
    OperatorDigestRecommendation,
    OperatorDigestResult,
    OperatorDigestSummary,
)
from core.services.crm_operator_digest_service import (
    SEVERITY_GREEN,
    SEVERITY_RED,
    SEVERITY_YELLOW,
    build_digest,
    build_handoff_metrics,
    build_missed_lead_metrics,
    build_recommendations,
    build_workload_summary,
    calculate_digest_severity,
    format_digest_text,
    sanitize_preview,
)

NOW = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)


@dataclass
class HF:
    status: str = "open"
    priority: str = "normal"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    assigned_at: datetime | None = None
    contacted_at: datetime | None = None
    resolved_at: datetime | None = None
    assigned_to_admin_id: str | None = None


@dataclass
class ML:
    severity: str = "medium"
    reason: str = "operator_waiting"


# ----------------------------- empty / safety -------------------------------


class TestEmptyDigest:
    def test_empty_handoffs_safe(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert isinstance(r, OperatorDigestResult)
        assert r.summary.total_open == 0

    def test_empty_severity_green(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert r.summary.severity == SEVERITY_GREEN

    def test_none_inputs_safe(self) -> None:
        r = build_digest(now=NOW, handoffs=None, missed_leads=None)
        assert r.summary.total_open == 0

    def test_default_now(self) -> None:
        r = build_digest()
        assert r.generated_at is not None

    def test_empty_workload_is_empty_list(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert r.workload == []

    def test_empty_recommendations_has_quiet(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert any("tinch" in rec.text.lower() for rec in r.recommendations)


# ------------------------------- counts -------------------------------------


class TestHandoffCounts:
    def test_counts_open(self) -> None:
        rows = [HF(status="open"), HF(status="open"), HF(status="open")]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["total_open"] == 3

    def test_counts_waiting_phone(self) -> None:
        rows = [HF(status="waiting_phone"), HF(status="waiting_phone")]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["waiting_phone"] == 2

    def test_counts_assigned(self) -> None:
        rows = [HF(status="assigned"), HF(status="assigned")]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["assigned"] == 2

    def test_counts_contacted_today(self) -> None:
        rows = [
            HF(status="contacted", contacted_at=NOW - timedelta(hours=1)),
            HF(status="contacted", contacted_at=NOW - timedelta(hours=2)),
            HF(status="contacted", contacted_at=NOW - timedelta(hours=48)),
        ]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["contacted_today"] == 2

    def test_counts_resolved_today(self) -> None:
        rows = [
            HF(status="resolved", resolved_at=NOW - timedelta(hours=3)),
            HF(status="resolved", resolved_at=NOW - timedelta(days=3)),
        ]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["resolved_today"] == 1

    def test_counts_expired_today(self) -> None:
        rows = [
            HF(status="expired", updated_at=NOW - timedelta(hours=2)),
            HF(status="expired", updated_at=NOW - timedelta(days=5)),
        ]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["expired_today"] == 1

    def test_counts_urgent_open(self) -> None:
        rows = [
            HF(status="open", priority="urgent"),
            HF(status="assigned", priority="urgent"),
            HF(status="resolved", priority="urgent"),  # not counted
        ]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["urgent_open"] == 2

    def test_counts_high_open(self) -> None:
        rows = [
            HF(status="waiting_phone", priority="high"),
            HF(status="assigned", priority="high"),
        ]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["high_open"] == 2

    def test_oldest_wait_minutes(self) -> None:
        rows = [
            HF(status="open", created_at=NOW - timedelta(minutes=45)),
            HF(status="open", created_at=NOW - timedelta(minutes=130)),
            HF(status="resolved", created_at=NOW - timedelta(days=10)),  # ignored
        ]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["oldest_wait_minutes"] == 130

    def test_oldest_wait_minutes_with_no_active(self) -> None:
        rows = [HF(status="resolved", created_at=NOW - timedelta(days=2))]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["oldest_wait_minutes"] == 0

    def test_naive_timestamps_handled(self) -> None:
        naive_created = datetime(2026, 5, 28, 6, 0)  # naive
        rows = [HF(status="open", created_at=naive_created)]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["oldest_wait_minutes"] > 0

    def test_handoff_dict_input_supported(self) -> None:
        rows = [{"status": "open", "priority": "urgent", "created_at": NOW - timedelta(hours=1)}]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["urgent_open"] == 1

    def test_unknown_status_ignored(self) -> None:
        rows = [HF(status="weird")]
        m = build_handoff_metrics(rows, now=NOW)
        assert m["total_open"] == 0
        assert m["assigned"] == 0


# ----------------------------- missed leads ---------------------------------


class TestMissedLeadCounts:
    def test_critical_count(self) -> None:
        m = build_missed_lead_metrics(
            [ML(severity="critical"), ML(severity="critical"), ML(severity="high")]
        )
        assert m["critical_missed"] == 2

    def test_high_count(self) -> None:
        m = build_missed_lead_metrics([ML(severity="high"), ML(severity="high")])
        assert m["high_missed"] == 2

    def test_hot_unanswered(self) -> None:
        m = build_missed_lead_metrics([ML(reason="hot_unanswered")])
        assert m["hot_unanswered"] == 1

    def test_operator_waiting(self) -> None:
        m = build_missed_lead_metrics([ML(reason="operator_waiting"), ML(reason="other")])
        assert m["operator_waiting"] == 1

    def test_phone_shared_no_followup(self) -> None:
        m = build_missed_lead_metrics([ML(reason="phone_shared_no_followup")])
        assert m["phone_shared_no_followup"] == 1

    def test_missed_dict_input(self) -> None:
        m = build_missed_lead_metrics([{"severity": "critical", "reason": "hot_unanswered"}])
        assert m["critical_missed"] == 1
        assert m["hot_unanswered"] == 1

    def test_total_missed(self) -> None:
        m = build_missed_lead_metrics([ML(), ML(), ML()])
        assert m["total_missed"] == 3


# ------------------------------ workload ------------------------------------


class TestWorkload:
    def test_workload_by_operator(self) -> None:
        rows = [
            HF(status="assigned", assigned_to_admin_id="alice"),
            HF(status="assigned", assigned_to_admin_id="alice"),
            HF(status="open", assigned_to_admin_id=None),
        ]
        w = build_workload_summary(rows, now=NOW)
        ids = {e.operator_id for e in w}
        assert "alice" in ids and "unassigned" in ids

    def test_workload_urgent_count(self) -> None:
        rows = [
            HF(status="assigned", priority="urgent", assigned_to_admin_id="bob"),
            HF(status="assigned", priority="urgent", assigned_to_admin_id="bob"),
            HF(status="assigned", priority="normal", assigned_to_admin_id="bob"),
        ]
        w = build_workload_summary(rows, now=NOW)
        assert next(e for e in w if e.operator_id == "bob").urgent_assigned == 2

    def test_workload_oldest_assigned_minutes(self) -> None:
        rows = [
            HF(
                status="assigned",
                assigned_at=NOW - timedelta(minutes=20),
                assigned_to_admin_id="carol",
            ),
            HF(
                status="assigned",
                assigned_at=NOW - timedelta(minutes=200),
                assigned_to_admin_id="carol",
            ),
        ]
        w = build_workload_summary(rows, now=NOW)
        assert next(e for e in w if e.operator_id == "carol").oldest_assigned_minutes == 200

    def test_workload_terminal_excluded(self) -> None:
        rows = [
            HF(status="resolved", assigned_to_admin_id="dan"),
            HF(status="cancelled", assigned_to_admin_id="dan"),
        ]
        w = build_workload_summary(rows, now=NOW)
        assert all(e.operator_id != "dan" for e in w)

    def test_workload_sorted_urgent_first(self) -> None:
        rows = [
            HF(status="assigned", priority="normal", assigned_to_admin_id="x"),
            HF(status="assigned", priority="urgent", assigned_to_admin_id="y"),
        ]
        w = build_workload_summary(rows, now=NOW)
        assert w[0].operator_id == "y"


# ------------------------------ severity ------------------------------------


class TestSeverity:
    def test_severity_green_when_quiet(self) -> None:
        assert calculate_digest_severity({}, {}) == SEVERITY_GREEN

    def test_severity_yellow_when_high(self) -> None:
        assert calculate_digest_severity({"high_open": 2}, {}) == SEVERITY_YELLOW

    def test_severity_yellow_when_high_missed(self) -> None:
        assert calculate_digest_severity({}, {"high_missed": 1}) == SEVERITY_YELLOW

    def test_severity_red_when_critical_missed(self) -> None:
        assert calculate_digest_severity({}, {"critical_missed": 1}) == SEVERITY_RED

    def test_severity_red_when_3_urgent_open(self) -> None:
        assert calculate_digest_severity({"urgent_open": 3}, {}) == SEVERITY_RED

    def test_severity_red_when_urgent_old(self) -> None:
        assert (
            calculate_digest_severity({"urgent_open": 1, "oldest_wait_minutes": 90}, {})
            == SEVERITY_RED
        )

    def test_severity_yellow_when_urgent_fresh(self) -> None:
        assert (
            calculate_digest_severity({"urgent_open": 1, "oldest_wait_minutes": 10}, {})
            == SEVERITY_YELLOW
        )

    def test_severity_yellow_when_oldest_above_two_hours(self) -> None:
        assert calculate_digest_severity({"oldest_wait_minutes": 130}, {}) == SEVERITY_YELLOW

    def test_full_digest_red_with_critical_missed(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[ML(severity="critical")])
        assert r.summary.severity == SEVERITY_RED

    def test_full_digest_yellow_with_one_high(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open", priority="high")], missed_leads=[])
        assert r.summary.severity == SEVERITY_YELLOW

    def test_full_digest_green_when_quiet(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="resolved")], missed_leads=[])
        assert r.summary.severity == SEVERITY_GREEN


# --------------------------- recommendations --------------------------------


class TestRecommendations:
    def test_rec_for_urgent(self) -> None:
        recs = build_recommendations({"urgent_open": 1}, {})
        assert any("urgent" in r.text.lower() for r in recs)

    def test_rec_for_waiting_phone(self) -> None:
        recs = build_recommendations({"waiting_phone": 1}, {})
        assert any("telefon" in r.text.lower() for r in recs)

    def test_rec_for_expired(self) -> None:
        recs = build_recommendations({"expired_today": 1}, {})
        assert any("expired" in r.text.lower() for r in recs)

    def test_rec_for_critical_missed(self) -> None:
        recs = build_recommendations({}, {"critical_missed": 1})
        assert any("critical" in r.text.lower() for r in recs)

    def test_rec_for_high_open(self) -> None:
        recs = build_recommendations({"high_open": 1}, {})
        assert any("high" in r.text.lower() for r in recs)

    def test_rec_for_hot_unanswered(self) -> None:
        recs = build_recommendations({}, {"hot_unanswered": 1})
        assert any("hot" in r.text.lower() for r in recs)

    def test_rec_ranks_are_sequential(self) -> None:
        recs = build_recommendations({"urgent_open": 1, "waiting_phone": 1, "expired_today": 1}, {})
        for i, r in enumerate(recs, start=1):
            assert r.rank == i

    def test_rec_default_when_quiet(self) -> None:
        recs = build_recommendations({}, {})
        assert len(recs) == 1
        assert recs[0].severity == "info"

    def test_rec_critical_first(self) -> None:
        recs = build_recommendations({"urgent_open": 1}, {"critical_missed": 1})
        assert recs[0].severity == "critical"


# ---------------------------- text formatting -------------------------------


class TestFormatDigestText:
    def test_format_digest_text_runs(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open")], missed_leads=[])
        text = format_digest_text(r)
        assert "CRM Operator Digest" in text
        assert "GREEN" in text or "YELLOW" in text or "RED" in text

    def test_no_raw_phone_in_text(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open")], missed_leads=[])
        text = format_digest_text(r)
        # Phone-like substrings should be redacted
        import re

        assert not re.search(r"\+?\d{7,}", text)

    def test_token_redacted_in_text(self) -> None:
        # sanitize_preview must scrub tokens
        cleaned = sanitize_preview("sk-abcdefghij1234567890")
        assert "[REDACTED]" in (cleaned or "")
        assert "sk-" not in (cleaned or "")

    def test_bearer_redacted(self) -> None:
        cleaned = sanitize_preview("Bearer abcdefghijklmnop")
        assert "Bearer" not in (cleaned or "")

    def test_no_fake_eta_in_text(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open")], missed_leads=[])
        text = format_digest_text(r)
        assert "ETA:" not in text
        assert "min ichida" not in text

    def test_no_user_greeting_in_text(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open")], missed_leads=[])
        text = format_digest_text(r)
        assert "Assalomu alaykum" not in text
        assert "Hurmatli mijoz" not in text

    def test_includes_recommendations(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open", priority="urgent")], missed_leads=[])
        text = format_digest_text(r)
        assert "Tavsiyalar" in text

    def test_includes_handoff_section(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open")], missed_leads=[])
        text = format_digest_text(r)
        assert "Handofflar" in text

    def test_includes_missed_lead_section(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[ML(severity="critical")])
        text = format_digest_text(r)
        assert "Missed" in text

    def test_workload_only_when_present(self) -> None:
        empty = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert "Operator yuklamasi" not in format_digest_text(empty)
        rich = build_digest(
            now=NOW,
            handoffs=[HF(status="assigned", assigned_to_admin_id="z")],
            missed_leads=[],
        )
        assert "Operator yuklamasi" in format_digest_text(rich)


# ------------------------------ sanitization --------------------------------


class TestSanitizePreview:
    def test_redact_token(self) -> None:
        assert "[REDACTED]" in (sanitize_preview("sk-abcdef12345") or "")

    def test_redact_bearer(self) -> None:
        assert "[REDACTED]" in (sanitize_preview("Bearer abcdef1234567890") or "")

    def test_redact_phone(self) -> None:
        assert "[PHONE]" in (sanitize_preview("+998901234567 keldi") or "")

    def test_redact_long_digits(self) -> None:
        # Contiguous 10+ digit run must be masked.
        assert "[PHONE]" in (sanitize_preview("998901234567") or "")

    def test_short_digits_not_redacted(self) -> None:
        assert sanitize_preview("rate 123") == "rate 123"

    def test_none_input_returns_none(self) -> None:
        assert sanitize_preview(None) is None

    def test_empty_input_returns_none(self) -> None:
        assert sanitize_preview("") is None

    def test_max_len_clamp(self) -> None:
        long = "x" * 5000
        assert len(sanitize_preview(long, max_len=100) or "") == 100


# ------------------------------- summary ------------------------------------


class TestSummaryDataclass:
    def test_summary_fields(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert isinstance(r.summary, OperatorDigestSummary)
        # Must have all the documented fields
        for f in (
            "severity",
            "total_open",
            "waiting_phone",
            "assigned",
            "contacted_today",
            "resolved_today",
            "expired_today",
            "urgent_open",
            "high_open",
            "oldest_wait_minutes",
            "total_missed",
            "critical_missed",
            "high_missed",
            "hot_unanswered",
        ):
            assert hasattr(r.summary, f)

    def test_recommendations_are_dataclass(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert all(isinstance(rec, OperatorDigestRecommendation) for rec in r.recommendations)

    def test_metrics_have_severity(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        for m in r.metrics:
            assert m.severity in {"info", "warning", "danger", "success"}

    def test_metrics_have_label(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        for m in r.metrics:
            assert m.label
