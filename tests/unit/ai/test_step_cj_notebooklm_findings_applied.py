"""Tests for Step CJ — NotebookLM Findings Applied to uz.md."""

from __future__ import annotations

from pathlib import Path


def _uz() -> str:
    return Path("shared/knowledge/uz.md").read_text(encoding="utf-8")


class TestBotSections:
    def test_bot_bolimlari_exists(self):
        assert "Bot bo'limlari" in _uz()

    def test_ai_yordam_mentioned(self):
        assert "AI yordam" in _uz()

    def test_narx_guidance(self):
        c = _uz()
        assert "Narx" in c and "taxminiy" in c.lower()

    def test_katalog_guidance(self):
        assert "Katalog" in _uz()

    def test_buyurtma_guidance(self):
        assert "Buyurtma" in _uz() or "Zakaz" in _uz()

    def test_operator_guidance(self):
        assert "Operator" in _uz()


class TestAIButtons:
    def test_ai_rejim_tugmalari(self):
        assert "AI rejim tugmalari" in _uz()

    def test_reset_guidance(self):
        assert "Reset" in _uz()

    def test_yordam_guidance(self):
        assert "Yordam" in _uz()


class TestOrderProcess:
    def test_buyurtma_jarayoni(self):
        c = _uz()
        assert "Buyurtma jarayoni" in c or "buyurtma" in c.lower()

    def test_admin_reviews(self):
        c = _uz()
        assert "operator" in c.lower() or "admin" in c.lower()

    def test_final_price_after_measurement(self):
        c = _uz()
        assert "o'lchovdan keyin" in c.lower()

    def test_no_yozib_qoydim(self):
        c = _uz()
        assert "yozib qo'ydim" in c and "DEMASIN" in c


class TestForbiddenClaims:
    def test_taqiqlangan_section(self):
        assert "Taqiqlangan" in _uz()

    def test_no_aniq_narx(self):
        c = _uz()
        assert "aniq narx" in c.lower()

    def test_no_usta_boradi(self):
        assert "usta boradi" in _uz().lower()

    def test_no_fake_eta(self):
        c = _uz().lower()
        assert "hozir bog'lanadi" in c or "operator hozir" in c

    def test_no_bugun_qilamiz(self):
        assert "bugun qilamiz" in _uz().lower()

    def test_no_eng_arzon(self):
        assert "eng arzon" in _uz().lower()

    def test_no_100_kafolat(self):
        assert "100% kafolat" in _uz()

    def test_no_maxsus_chegirma(self):
        c = _uz().lower()
        assert "maxsus chegirma" in c


class TestPaymentRules:
    def test_payment_section(self):
        c = _uz().lower()
        assert "to'lov" in c

    def test_no_payme_click_claim(self):
        c = _uz()
        assert "Payme" in c or "Click" in c

    def test_admin_reviews_payment(self):
        c = _uz().lower()
        assert "admin" in c or "ko'rib chiq" in c


class TestPackages:
    def test_paketlar_section(self):
        c = _uz().lower()
        assert "paket" in c or "xizmat tur" in c

    def test_no_invented_vip_price(self):
        c = _uz()
        lines = [ln for ln in c.splitlines() if "VIP" in ln]
        for line in lines:
            assert "000" not in line or "razmer" in line.lower()


class TestDiscount:
    def test_discount_section(self):
        c = _uz().lower()
        assert "chegirma" in c

    def test_discount_20m2(self):
        assert "20 m" in _uz() and "5%" in _uz()

    def test_discount_40m2(self):
        assert "40 m" in _uz() and "10%" in _uz()

    def test_no_invented_discount(self):
        c = _uz().lower()
        assert "o'ylab topmasin" in c or "rasmiy aksiya" in c


class TestOperatorRules:
    def test_operator_section(self):
        c = _uz().lower()
        assert "operatorga ulash" in c or "operator" in c

    def test_no_fake_eta_rule(self):
        c = _uz()
        assert "aniq vaqt" in c.lower()

    def test_asks_phone(self):
        assert "telefon" in _uz().lower()


class TestNoSecrets:
    def test_no_token_pattern(self):
        c = _uz()
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_openai_key(self):
        assert "OPENAI_API_KEY" not in _uz()

    def test_no_db_url(self):
        assert "postgresql://" not in _uz()


class TestTaxminiyWarning:
    def test_taxminiy_after_table(self):
        c = _uz()
        assert "TAXMINIY" in c
