"""Tests for Step Q — Multilingual + Fuzzy intent detection via LeadSignalService."""
from __future__ import annotations

from core.services.lead_signal_service import LeadSignalService

svc = LeadSignalService


# ─── Uzbek Cyrillic intent tests ─────────────────────────────────────────────


class TestUzbekCyrillicIntent:
    def test_narxi_qancha_cyr(self):
        r = svc.extract_signals("нархи қанча")
        assert r.intent == "wants_price"

    def test_qimmat_cyr(self):
        r = svc.extract_signals("қиммат")
        assert r.objection_type == "price"

    def test_operator_kerak_cyr(self):
        r = svc.extract_signals("оператор керак")
        assert r.intent == "wants_operator"

    def test_kafolat_bormi_cyr(self):
        r = svc.extract_signals("кафолат борми")
        assert r.objection_type == "trust"

    def test_chegirma_bormi_cyr(self):
        r = svc.extract_signals("чегирма борми")
        assert r.intent == "wants_discount"

    def test_buyurtma_cyr(self):
        r = svc.extract_signals("буюртма бермоқчиман")
        assert r.intent == "wants_order"

    def test_usta_cyr(self):
        r = svc.extract_signals("уста чақиринг")
        assert r.intent == "wants_measurement"

    def test_kerak_emas_cyr(self):
        r = svc.extract_signals("керак эмас")
        assert r.intent == "stop_request"

    def test_ertaga_kerak_cyr(self):
        r = svc.extract_signals("эртага керак")
        assert r.urgency == "high"

    def test_bugun_cyr(self):
        r = svc.extract_signals("бугун келинг")
        assert r.urgency == "high"

    def test_katalog_cyr(self):
        r = svc.extract_signals("каталог кўрсатинг")
        assert r.intent == "wants_catalog"


# ─── Typo/fuzzy intent tests ─────────────────────────────────────────────────


class TestTypoFuzzyIntent:
    def test_narhi_qancha(self):
        r = svc.extract_signals("narhi qancha")
        assert r.intent == "wants_price"

    def test_narx_qanca(self):
        r = svc.extract_signals("narx qanca")
        assert r.intent == "wants_price"

    def test_narxi_qncha(self):
        r = svc.extract_signals("narxi qncha")
        assert r.intent == "wants_price"

    def test_qmat_ekan(self):
        r = svc.extract_signals("qmat ekan")
        assert r.objection_type == "price"

    def test_qimatt(self):
        r = svc.extract_signals("qimatt ekan")
        assert r.objection_type == "price"

    def test_opirator_kere(self):
        r = svc.extract_signals("opirator kere")
        assert r.intent == "wants_operator"

    def test_aperator_kerak(self):
        r = svc.extract_signals("aperator kerak")
        assert r.intent == "wants_operator"

    def test_zakas_bermoqchiman(self):
        r = svc.extract_signals("zakas bermoqchiman")
        assert r.intent == "wants_order"

    def test_skidka_bomi(self):
        r = svc.extract_signals("skidka bomi")
        assert r.intent == "wants_discount"

    def test_kafalat_bormi(self):
        r = svc.extract_signals("kafalat bormi")
        assert r.objection_type == "trust"


# ─── Mixed script tests ──────────────────────────────────────────────────────


class TestMixedScript:
    def test_narx_skolko(self):
        r = svc.extract_signals("narx сколько")
        assert r.intent == "wants_price"

    def test_qimmat_dorogo(self):
        r = svc.extract_signals("qimmat дорого")
        assert r.objection_type == "price"

    def test_operator_pozvanite(self):
        r = svc.extract_signals("operator позвоните")
        assert r.intent == "wants_operator"

    def test_katalog_foto(self):
        r = svc.extract_signals("katalog фото")
        assert r.intent == "wants_catalog"

    def test_garantiya_bormi(self):
        r = svc.extract_signals("гарантия bormi")
        assert r.objection_type == "trust"


# ─── Voice transcription tests ───────────────────────────────────────────────


class TestVoiceTranscription:
    def test_narx_qancha_boladi(self):
        r = svc.extract_signals("narx qancha boladi")
        assert r.intent == "wants_price"

    def test_qancha_boladi(self):
        r = svc.extract_signals("qancha bo'ladi")
        assert r.intent == "wants_price"

    def test_ustani_chaqirish_kerak_edi(self):
        r = svc.extract_signals("ustani chaqirish kerak edi")
        assert r.intent == "wants_measurement"

    def test_gulli_patalok_qancha_ekan(self):
        r = svc.extract_signals("gulli patalok qancha ekan")
        assert r.intent == "wants_price"

    def test_menga_operator_kerak_edi(self):
        r = svc.extract_signals("menga operator kerak edi")
        assert r.intent == "wants_operator"

    def test_bugun_olchovga_keladimi(self):
        r = svc.extract_signals("bugun o'lchovga keladimi")
        assert r.urgency == "high"

    def test_ertaga_ornatish_kerak_edi(self):
        r = svc.extract_signals("ertaga o'rnatish kerak edi")
        assert r.urgency == "high"


# ─── Russian transliteration tests ───────────────────────────────────────────


class TestRussianTransliteration:
    def test_skolko_stoit(self):
        r = svc.extract_signals("skolko stoit")
        assert r.intent == "wants_price"

    def test_dorogo(self):
        r = svc.extract_signals("dorogo")
        assert r.objection_type == "price"

    def test_pozvonite(self):
        r = svc.extract_signals("pozvonite")
        assert r.intent == "wants_operator"

    def test_zakazat(self):
        r = svc.extract_signals("zakazat")
        assert r.intent == "wants_order"

    def test_skidka_est(self):
        r = svc.extract_signals("skidka est")
        assert r.intent == "wants_discount"


# ─── Safety: stop still works ────────────────────────────────────────────────


class TestStopSafety:
    def test_kerak_emas_exact(self):
        r = svc.extract_signals("kerak emas")
        assert r.intent == "stop_request"

    def test_operator_kerak_not_stop(self):
        r = svc.extract_signals("оператор керак")
        assert r.intent != "stop_request"

    def test_menga_kerak_emas(self):
        r = svc.extract_signals("menga kerak emas")
        assert r.intent == "stop_request"

    def test_yozmang_iltimos(self):
        r = svc.extract_signals("yozmang iltimos")
        assert r.intent == "stop_request"

    def test_kerak_emas_cyrillic(self):
        r = svc.extract_signals("керак эмас")
        assert r.intent == "stop_request"


# ─── Safety: short words don't over-trigger ──────────────────────────────────


class TestShortWordSafety:
    def test_ha_unclear(self):
        r = svc.extract_signals("ha")
        assert r.intent == "unclear"

    def test_ok_unclear(self):
        r = svc.extract_signals("ok")
        assert r.intent == "unclear"

    def test_kerak_alone_weak(self):
        r = svc.extract_signals("kerak")
        assert r.intent == "wants_order"
        assert r.confidence_score <= 60

    def test_emoji_unclear(self):
        r = svc.extract_signals("👍")
        assert r.intent == "unclear"


# ─── Area detection with typos ───────────────────────────────────────────────


class TestAreaWithTypos:
    def test_20_kv_qanca(self):
        r = svc.extract_signals("20 kv qanca")
        assert r.intent == "wants_price"
        assert r.area_m2 == 20.0

    def test_5x4_qanca(self):
        r = svc.extract_signals("5x4 qanca")
        assert r.area_m2 == 20.0
        assert r.intent == "wants_price"

    def test_30_m2_narhi(self):
        r = svc.extract_signals("30 m2 narhi")
        assert r.area_m2 == 30.0
        assert r.intent == "wants_price"


# ─── Language detection in signals ───────────────────────────────────────────


class TestLanguageInSignals:
    def test_uzbek_cyrillic_detected(self):
        r = svc.extract_signals("нархи қанча")
        assert r.language == "uz"

    def test_russian_detected(self):
        r = svc.extract_signals("сколько стоит")
        assert r.language == "ru"

    def test_uzbek_latin_default(self):
        r = svc.extract_signals("narxi qancha")
        assert r.language == "uz"

    def test_mixed_defaults_uz(self):
        r = svc.extract_signals("narx сколько")
        assert r.language in ("uz", "ru")


# ─── Confidence levels ───────────────────────────────────────────────────────


class TestConfidenceLevels:
    def test_exact_strong_high_confidence(self):
        r = svc.extract_signals("narxi qancha")
        assert r.confidence_score >= 40

    def test_fuzzy_match_still_detects(self):
        r = svc.extract_signals("narhi qanca")
        assert r.intent == "wants_price"

    def test_unclear_low_confidence(self):
        r = svc.extract_signals("salom dunyo")
        assert r.confidence_score < 30


# ─── Additional Russian Cyrillic passthrough ─────────────────────────────────


class TestRussianCyrillicPassthrough:
    def test_skolko_stoit_cyrillic(self):
        r = svc.extract_signals("сколько стоит")
        assert r.intent == "wants_price"

    def test_dorogo_cyrillic(self):
        r = svc.extract_signals("дорого")
        assert r.objection_type == "price"

    def test_pozvanite_cyrillic(self):
        r = svc.extract_signals("позвоните")
        assert r.intent == "wants_operator"

    def test_srochno_cyrillic(self):
        r = svc.extract_signals("срочно")
        assert r.urgency == "high"
