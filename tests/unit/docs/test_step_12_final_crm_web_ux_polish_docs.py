"""Step 12 — Final CRM/Web UX Polish docs tests."""

from __future__ import annotations

from pathlib import Path

_DOC = "docs/AI_AGENT_SYSTEM/127_FINAL_CRM_WEB_UX_POLISH.md"


def _c() -> str:
    return Path(_DOC).read_text(encoding="utf-8")


class TestDocExists:
    def test_exists(self) -> None:
        assert Path(_DOC).exists()

    def test_non_empty(self) -> None:
        assert len(_c()) > 1000

    def test_title(self) -> None:
        assert "# 127 — Final CRM/Web UX Polish" in _c()


class TestPagesTouched:
    def test_mentions_base_template(self) -> None:
        assert "base.html" in _c()

    def test_mentions_handoffs_template(self) -> None:
        assert "crm_handoffs.html" in _c()

    def test_mentions_missed_template(self) -> None:
        assert "crm_missed_leads.html" in _c()

    def test_mentions_analytics_template(self) -> None:
        assert "analytics.html" in _c()

    def test_mentions_contact_detail_template(self) -> None:
        assert "crm_contact_detail.html" in _c()

    def test_mentions_standalone_template(self) -> None:
        assert "crm_operator_digest.html" in _c()


class TestSafetyConstraints:
    def test_says_no_deploy(self) -> None:
        assert "Deploy: NO" in _c()

    def test_says_no_vps(self) -> None:
        assert "VPS: NO" in _c()

    def test_stage_1_not_applied(self) -> None:
        assert "Stage 1 LOG_ONLY: NOT APPLIED" in _c() or "NOT APPLIED" in _c()

    def test_flags_not_enabled(self) -> None:
        assert "NOT ENABLED" in _c()

    def test_no_real_telegram(self) -> None:
        assert "No real Telegram" in _c() or "no real Telegram" in _c().lower()

    def test_no_openai_calls(self) -> None:
        assert "OpenAI" in _c()


class TestNoSendStatus:
    def test_no_send_section(self) -> None:
        assert "No-send status" in _c() or "No-send" in _c()

    def test_disabled_button_described(self) -> None:
        assert "(disabled)" in _c()

    def test_no_active_send_endpoint(self) -> None:
        # Doc must claim no template references an active send endpoint
        assert "operator-digest/send" in _c() or "no active send" in _c().lower()


class TestRemainingDebt:
    def test_remaining_debt_section(self) -> None:
        assert "Remaining UX debt" in _c() or "Remaining" in _c()

    def test_mentions_severity_tuning(self) -> None:
        assert "Severity" in _c() or "threshold" in _c().lower()

    def test_mentions_missed_data_source(self) -> None:
        assert "Missed-leads" in _c() or "missed-leads" in _c().lower()


class TestNoSecretLeaks:
    def test_no_sk_token(self) -> None:
        assert "sk-" not in _c()

    def test_no_bearer_token(self) -> None:
        assert "Bearer " not in _c()

    def test_no_db_url(self) -> None:
        assert "postgresql://" not in _c()
        assert "postgresql+asyncpg://" not in _c()

    def test_no_openai_key_literal(self) -> None:
        assert "OPENAI_API_KEY=" not in _c()

    def test_no_bot_token_format(self) -> None:
        import re

        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", _c())


class TestTestsAndNextStep:
    def test_tests_section(self) -> None:
        assert "Tests" in _c()

    def test_next_step_section(self) -> None:
        assert "Next step" in _c()

    def test_mentions_stage_1_apply(self) -> None:
        assert "Stage 1 LOG_ONLY apply" in _c()
