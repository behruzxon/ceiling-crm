"""Tests for Step CR — Stage 1 Final Apply Pack."""
from __future__ import annotations

from pathlib import Path

_DOC = "docs/AI_AGENT_SYSTEM/108_STAGE_1_FINAL_APPLY_PACK_LATEST.md"


def _c() -> str:
    return Path(_DOC).read_text(encoding="utf-8")


class TestDocExists:
    def test_exists(self):
        assert Path(_DOC).exists()


class TestBaseline:
    def test_latest_commit(self):
        assert "a1216e2" in _c()

    def test_branch_name(self):
        assert "feature/vash-ai-hardening-session" in _c()

    def test_test_count(self):
        assert "5520" in _c()

    def test_deploy_no(self):
        assert "Deploy" in _c() and "NO" in _c()

    def test_vps_no(self):
        assert "VPS" in _c() and "NO" in _c()

    def test_flags_not_enabled(self):
        assert "NOT ENABLED" in _c()

    def test_stage1_not_applied(self):
        assert "NOT APPLIED" in _c()


class TestPreApply:
    def test_db_backup(self):
        c = _c().lower()
        assert "backup" in c

    def test_alembic(self):
        assert "alembic upgrade head" in _c()

    def test_log_only(self):
        assert "LOG_ONLY" in _c()

    def test_forbids_live_sender(self):
        c = _c()
        assert "LIVE_SENDER" in c

    def test_forbids_followups(self):
        c = _c()
        assert "FOLLOWUPS" in c

    def test_forbids_campaign_send(self):
        c = _c()
        assert "CAMPAIGN_SEND" in c


class TestScenarios:
    def test_price_calculator(self):
        c = _c()
        assert "20 kv gulli" in c

    def test_led_price(self):
        c = _c()
        assert "5x4 led" in c

    def test_compare_objection(self):
        c = _c()
        assert "boshqalar arzon" in c

    def test_operator_handoff(self):
        c = _c()
        assert "operator kerak" in c

    def test_stop_scenario(self):
        c = _c()
        assert "kerak emas" in c

    def test_cyrillic(self):
        c = _c()
        assert "нархи" in c or "Cyrillic" in c


class TestObservation:
    def test_30_min(self):
        assert "30 min" in _c()

    def test_24h(self):
        assert "24h" in _c()


class TestRollback:
    def test_rollback_steps(self):
        c = _c()
        assert "Rollback" in c
        assert "OFF" in c

    def test_stop_triggers(self):
        c = _c()
        assert "STOP" in c
        assert "Health RED" in c


class TestNoSecrets:
    def test_not_deployed(self):
        c = _c()
        assert "deployed to production" not in c.lower()

    def test_not_applied(self):
        assert "NOT APPLIED" in _c()

    def test_no_token(self):
        c = _c()
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_openai_key(self):
        assert "OPENAI_API_KEY=" not in _c()

    def test_no_db_url(self):
        assert "postgresql://" not in _c()


class TestSmoke:
    def test_bot(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_price(self):
        from core.services.price_calculator_service import (
            PriceCalculatorService,
        )
        assert PriceCalculatorService is not None

    def test_handoff(self):
        from core.services.crm_operator_handoff_service import (
            build_user_message,
        )
        assert callable(build_user_message)
