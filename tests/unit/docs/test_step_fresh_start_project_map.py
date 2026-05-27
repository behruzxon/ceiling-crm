"""Tests for Fresh Start Project Map."""

from __future__ import annotations

from pathlib import Path

_DOC = "docs/AI_AGENT_SYSTEM/115_FRESH_START_PROJECT_MAP.md"


def _c() -> str:
    return Path(_DOC).read_text(encoding="utf-8")


class TestDocExists:
    def test_exists(self):
        assert Path(_DOC).exists()


class TestCurrentState:
    def test_contains_telegram_bot(self):
        assert "Telegram" in _c()

    def test_contains_ai_assistant(self):
        assert "AI" in _c()

    def test_contains_price_calculator(self):
        assert "Price Calculator" in _c()

    def test_contains_operator_handoff(self):
        assert "Operator Handoff" in _c() or "handoff" in _c().lower()

    def test_contains_crm_web(self):
        assert "CRM" in _c()

    def test_contains_tests_count(self):
        assert "5625" in _c() or "5051" in _c()


class TestStrengths:
    def test_strengths_section(self):
        assert "Strong" in _c()

    def test_scores_present(self):
        assert "/10" in _c()


class TestMissing:
    def test_missing_section(self):
        assert "Missing" in _c() or "missing" in _c()

    def test_handoff_queue_view(self):
        c = _c().lower()
        assert "handoff" in c and "web" in c


class TestNext10Steps:
    def test_next_steps(self):
        assert "Next 10" in _c() or "Step" in _c()

    def test_ordered(self):
        assert "| 1 |" in _c() and "| 10 |" in _c()


class TestSafety:
    def test_deploy_no(self):
        assert "Deploy" in _c() and "NO" in _c()

    def test_stage1_not_applied(self):
        assert "NOT APPLIED" in _c()

    def test_live_features_not_enabled(self):
        c = _c()
        assert "Live sender" in c or "live sender" in c.lower()
        assert "Do NOT" in c or "NOT Touch" in c

    def test_no_token(self):
        c = _c()
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_openai_key(self):
        assert "OPENAI_API_KEY=" not in _c()

    def test_no_db_url(self):
        assert "postgresql://" not in _c()


class TestRecommendation:
    def test_has_recommendation(self):
        assert "Recommendation" in _c() or "recommendation" in _c()
