"""Tests for Step CI — NotebookLM Knowledge Review Pack."""
from __future__ import annotations

from pathlib import Path

_D = "docs/AI_AGENT_SYSTEM"
_SP = f"{_D}/95_NOTEBOOKLM_SOURCE_PACK.md"
_RP = f"{_D}/96_NOTEBOOKLM_REVIEW_PROMPTS.md"
_UP = f"{_D}/97_AI_KNOWLEDGE_UPDATE_PLAN_FROM_NOTEBOOKLM.md"


def _sp() -> str:
    return Path(_SP).read_text(encoding="utf-8")


def _rp() -> str:
    return Path(_RP).read_text(encoding="utf-8")


def _up() -> str:
    return Path(_UP).read_text(encoding="utf-8")


class TestDocsExist:
    def test_source_pack(self):
        assert Path(_SP).exists()

    def test_review_prompts(self):
        assert Path(_RP).exists()

    def test_update_plan(self):
        assert Path(_UP).exists()


class TestSourcePackContent:
    def test_business_summary(self):
        assert "Vashpotolok" in _sp()

    def test_commands(self):
        assert "/start" in _sp()
        assert "/ai_help" in _sp()

    def test_main_buttons(self):
        assert "Zakaz" in _sp()
        assert "Narx" in _sp()

    def test_ai_buttons(self):
        assert "Katalog" in _sp()
        assert "Operator" in _sp()
        assert "Reset" in _sp()

    def test_catalog_flow(self):
        assert "Catalog Flow" in _sp() or "catalog" in _sp().lower()

    def test_pricing_flow(self):
        assert "Pricing Flow" in _sp() or "pricing" in _sp().lower()

    def test_order_flow(self):
        assert "Order Flow" in _sp()

    def test_operator_handoff(self):
        assert "Operator Handoff" in _sp() or "operator" in _sp().lower()

    def test_measurement_flow(self):
        assert "Measurement" in _sp()

    def test_safety_rules(self):
        assert "Safety Rules" in _sp()

    def test_forbidden_claims(self):
        assert "Forbidden" in _sp() or "forbidden" in _sp().lower()

    def test_no_secrets_warning(self):
        assert "DO NOT UPLOAD" in _sp()

    def test_final_price_after_measurement(self):
        c = _sp().lower()
        assert "o'lchovdan keyin" in c or "measurement" in c

    def test_no_fake_discount(self):
        c = _sp().lower()
        assert "fake discount" in c or "no fake" in c

    def test_no_same_day_promise(self):
        c = _sp().lower()
        assert "bugun qilamiz" in c

    def test_no_fake_eta(self):
        c = _sp().lower()
        assert "fake eta" in c or "no fake" in c

    def test_gaps_section(self):
        assert "Gaps" in _sp() or "gaps" in _sp().lower()

    def test_questions_section(self):
        assert "Questions" in _sp() or "NotebookLM" in _sp()


class TestReviewPrompts:
    def test_knowledge_gap_prompt(self):
        assert "Knowledge Gap" in _rp() or "gap" in _rp().lower()

    def test_faq_prompt(self):
        assert "FAQ" in _rp()

    def test_button_validation_prompt(self):
        c = _rp()
        assert "Button" in c or "button" in c

    def test_pricing_safety_prompt(self):
        assert "Pricing Safety" in _rp() or "pricing" in _rp().lower()

    def test_operator_safety_prompt(self):
        assert "Operator" in _rp()

    def test_catalog_flow_prompt(self):
        assert "Catalog" in _rp() or "catalog" in _rp().lower()

    def test_uzbek_russian_prompt(self):
        c = _rp()
        assert "Uzbek" in c or "Russian" in c

    def test_final_summary_prompt(self):
        assert "Summary" in _rp() or "summary" in _rp().lower()


class TestUpdatePlan:
    def test_accepted_rejected_field(self):
        assert "Accepted" in _up()

    def test_target_file_field(self):
        assert "Target File" in _up()

    def test_tests_needed_field(self):
        assert "Tests Needed" in _up()

    def test_risk_field(self):
        assert "Risk" in _up()

    def test_not_applied_disclaimer(self):
        c = _up()
        assert "NOT" in c
        assert "applied" in c.lower() or "deployed" in c.lower()


class TestNoSecrets:
    def test_no_token_in_source_pack(self):
        c = _sp()
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_openai_key(self):
        c = _sp()
        assert "OPENAI_API_KEY=" not in c

    def test_no_db_url(self):
        c = _sp()
        assert "postgresql://" not in c
        assert "redis://" not in c

    def test_no_token_in_prompts(self):
        c = _rp()
        assert "sk-proj-" not in c
        assert "BOT_TOKEN=" not in c

    def test_no_deployed_claim(self):
        c = _sp()
        assert "deployed to production" not in c.lower()

    def test_no_stage1_applied_claim(self):
        c = _sp()
        assert "Stage 1 applied" not in c
        assert "NOT applied" in c or "NOT APPLIED" in c
