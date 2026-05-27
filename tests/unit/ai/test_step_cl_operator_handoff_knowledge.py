"""Tests for Step CL — Operator Handoff Knowledge Updates."""
from __future__ import annotations

from pathlib import Path


def _uz() -> str:
    return Path("shared/knowledge/uz.md").read_text(encoding="utf-8")


def _prompt() -> str:
    return Path("apps/bot/ai/system_prompt.py").read_text(encoding="utf-8")


class TestUzMdOperatorQueue:
    def test_operator_handoff_queue(self):
        c = _uz()
        assert "queuega tushadi" in c or "queue" in c.lower()

    def test_phone_missing_asks(self):
        assert "telefon" in _uz().lower()

    def test_operator_reviews(self):
        c = _uz().lower()
        assert "ko'rib chiqadi" in c or "ko'rib chiq" in c

    def test_no_exact_eta(self):
        c = _uz()
        assert "aniq vaqt" in c.lower()

    def test_no_same_day_promise_as_claim(self):
        c = _uz()
        assert "Bugun bog'lanadi" not in c or "DEMASLIK" in c

    def test_user_can_write_more(self):
        c = _uz().lower()
        assert "qo'shimcha savol" in c or "savol yozish" in c

    def test_dedup_mentioned(self):
        c = _uz().lower()
        assert "takroriy" in c or "mavjud" in c


class TestPromptOperatorSafety:
    def test_no_fake_eta_rule(self):
        c = _prompt().lower()
        assert "aniq vaqt" in c

    def test_ask_phone_rule(self):
        c = _prompt().lower()
        assert "telefon" in c and "operator" in c

    def test_hozir_blocked_rule(self):
        c = _uz()
        assert "hozir" in c.lower() and "DEMASLIK" in c

    def test_no_bugun_keladi(self):
        c = _uz()
        assert "bugun keladi" not in c


class TestDocExists:
    def test_handoff_doc(self):
        p = "docs/AI_AGENT_SYSTEM/99_OPERATOR_HANDOFF_QUEUE_ETA_SAFE_FLOW.md"
        assert Path(p).exists()

    def test_doc_contains_queue(self):
        p = "docs/AI_AGENT_SYSTEM/99_OPERATOR_HANDOFF_QUEUE_ETA_SAFE_FLOW.md"
        c = Path(p).read_text(encoding="utf-8")
        assert "Queue" in c or "queue" in c

    def test_doc_contains_no_eta(self):
        p = "docs/AI_AGENT_SYSTEM/99_OPERATOR_HANDOFF_QUEUE_ETA_SAFE_FLOW.md"
        c = Path(p).read_text(encoding="utf-8")
        assert "No-ETA" in c or "no-ETA" in c or "ETA" in c

    def test_doc_contains_priority(self):
        p = "docs/AI_AGENT_SYSTEM/99_OPERATOR_HANDOFF_QUEUE_ETA_SAFE_FLOW.md"
        c = Path(p).read_text(encoding="utf-8")
        assert "urgent" in c.lower()

    def test_doc_contains_dedup(self):
        p = "docs/AI_AGENT_SYSTEM/99_OPERATOR_HANDOFF_QUEUE_ETA_SAFE_FLOW.md"
        c = Path(p).read_text(encoding="utf-8")
        assert "dedup" in c.lower() or "Dedup" in c


class TestMigration:
    def test_migration_exists(self):
        p = Path(
            "infrastructure/database/migrations/versions/"
            "20260527_0530_n1o2p3q4r5s6_add_crm_operator_handoff_requests.py",
        )
        assert p.exists()

    def test_migration_has_create_table(self):
        p = Path(
            "infrastructure/database/migrations/versions/"
            "20260527_0530_n1o2p3q4r5s6_add_crm_operator_handoff_requests.py",
        )
        c = p.read_text(encoding="utf-8")
        assert "create_table" in c
        assert "crm_operator_handoff_requests" in c

    def test_migration_has_downgrade(self):
        p = Path(
            "infrastructure/database/migrations/versions/"
            "20260527_0530_n1o2p3q4r5s6_add_crm_operator_handoff_requests.py",
        )
        c = p.read_text(encoding="utf-8")
        assert "drop_table" in c


class TestSmoke:
    def test_bot_dispatcher(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_ai_support(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
