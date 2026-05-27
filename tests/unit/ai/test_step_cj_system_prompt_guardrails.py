"""Tests for Step CJ — System Prompt Guardrails."""

from __future__ import annotations

from pathlib import Path


def _prompt_src() -> str:
    return Path("apps/bot/ai/system_prompt.py").read_text(encoding="utf-8")


def _prompt_text() -> str:
    from apps.bot.ai.system_prompt import _SYSTEM_PROMPT

    return _SYSTEM_PROMPT


class TestPromptVersion:
    def test_version_exists(self):
        from apps.bot.ai.system_prompt import PROMPT_VERSION

        assert PROMPT_VERSION is not None

    def test_version_current(self):
        from apps.bot.ai.system_prompt import PROMPT_VERSION

        assert "cj" in PROMPT_VERSION or "2026" in PROMPT_VERSION

    def test_version_in_source(self):
        assert "PROMPT_VERSION" in _prompt_src()


class TestButtonFlowGuidance:
    def test_button_flow_section(self):
        c = _prompt_text()
        assert "BUTTON" in c or "FLOW" in c

    def test_buyurtma_guidance(self):
        c = _prompt_text().lower()
        assert "buyurtma" in c or "zakaz" in c

    def test_katalog_guidance(self):
        c = _prompt_text().lower()
        assert "katalog" in c

    def test_operator_guidance(self):
        c = _prompt_text().lower()
        assert "operator" in c

    def test_yordam_guidance(self):
        c = _prompt_text().lower()
        assert "yordam" in c or "tugma" in c


class TestPriceSafety:
    def test_narx_xavfsizligi_section(self):
        c = _prompt_text()
        assert "NARX XAVFSIZLIGI" in c or "TAXMINIY" in c

    def test_taxminiy_mentioned(self):
        assert "taxminiy" in _prompt_text().lower()

    def test_olchovdan_keyin(self):
        c = _prompt_text().lower()
        assert "o'lchovdan keyin" in c

    def test_aniq_narx_blocked(self):
        c = _prompt_text().lower()
        assert "aniq narx" in c and "dema" in c

    def test_final_narx_blocked(self):
        c = _prompt_text().lower()
        assert "final narx" in c and "dema" in c

    def test_maxsus_chegirma_blocked(self):
        c = _prompt_text().lower()
        assert "maxsus chegirma" in c or "o'ylab topma" in c


class TestOrderOperatorSafety:
    def test_yozib_qoydim_blocked(self):
        c = _prompt_text().lower()
        assert "yozib qo'ydim" in c

    def test_usta_boradi_blocked(self):
        c = _prompt_text().lower()
        assert "usta boradi" in c

    def test_bugun_qilamiz_blocked(self):
        c = _prompt_text().lower()
        assert "bugun qilamiz" in c

    def test_eng_arzon_blocked(self):
        c = _prompt_text().lower()
        assert "eng arzon" in c

    def test_100_kafolat_blocked(self):
        c = _prompt_text()
        assert "100%" in c

    def test_operator_no_fake_eta(self):
        c = _prompt_text().lower()
        assert "aniq vaqt" in c and "va'da" in c

    def test_no_payme_click_claim(self):
        c = _prompt_text().lower()
        assert "payme" in c or "click" in c


class TestForbiddenClaims:
    def test_forbidden_section(self):
        c = _prompt_text()
        assert "TAQIQLANGAN" in c

    def test_fsm_only_recording(self):
        c = _prompt_text().lower()
        assert "fsm" in c


class TestMediaSafety:
    def test_no_invented_media(self):
        c = _prompt_text().lower()
        assert "o'ylab topma" in c or "media bor deb" in c


class TestPromptNoSecrets:
    def test_no_token(self):
        c = _prompt_src()
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_bot_token(self):
        assert "BOT_TOKEN=" not in _prompt_src()

    def test_no_db_url(self):
        assert "postgresql://" not in _prompt_src()


class TestPromptLength:
    def test_prompt_not_too_long(self):
        assert len(_prompt_text()) < 20_000

    def test_prompt_not_empty(self):
        assert len(_prompt_text()) > 1000


class TestSmoke:
    def test_parse_ai_scoring(self):
        from apps.bot.ai.system_prompt import _parse_ai_scoring

        temp, conf = _parse_ai_scoring(
            {"lead_temperature": "hot", "closing_confidence": 0.8},
        )
        assert temp == "hot"
        assert conf == 0.8

    def test_injection_refusal(self):
        from apps.bot.ai.system_prompt import INJECTION_REFUSAL

        assert INJECTION_REFUSAL["intent"] == "other"
