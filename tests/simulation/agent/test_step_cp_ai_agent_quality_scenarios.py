"""Tests for Step CP — AI Agent Quality Scenarios (100 scenarios)."""
from __future__ import annotations

from core.schemas.agent_quality_simulator import AgentScenario
from core.services.agent_quality_simulator_service import (
    AgentQualitySimulatorService,
)

svc = AgentQualitySimulatorService()


def _run(text: str, cat: str = "price"):
    return svc.run_scenario(AgentScenario(text=text, category=cat))


class TestPriceDesignOrder:
    def test_20kv_qancha(self):
        r = _run("20 kv narx qancha")
        assert r.is_price_query and r.score >= 3

    def test_20kv_gulli(self):
        r = _run("20 kv gulli qancha")
        assert r.price_estimate_total and r.price_estimate_total > 0

    def test_5x4_led(self):
        r = _run("5x4 led qancha")
        assert r.area_parsed == 20.0 and r.design_parsed == "hi-tech"

    def test_oddiy(self):
        r = _run("oddiy nech pul")
        assert r.design_parsed == "adnatonniy"

    def test_mramor_narx(self):
        r = _run("mramor narx qancha")
        assert r.design_parsed == "mramor"

    def test_qora_uf(self):
        r = _run("qora uf narx")
        assert r.design_parsed == "qora uf"

    def test_100kv(self):
        r = _run("100 kv narx")
        assert r.area_parsed == 100.0

    def test_gulli_asks_area(self):
        r = _run("gulli potolok qancha")
        assert r.clarification_needed == "area"

    def test_20kv_asks_design(self):
        r = _run("20 kv xona narx")
        assert r.clarification_needed == "design"

    def test_kosmos_20kv(self):
        r = _run("20 kv kosmos")
        assert r.price_estimate_total and r.price_estimate_total > 0

    def test_osmon_30kv(self):
        r = _run("30 kv osmon narx")
        assert r.area_parsed == 30.0

    def test_hi_tech_5x5(self):
        r = _run("5x5 hi-tech")
        assert r.area_parsed == 25.0 and r.design_parsed == "hi-tech"

    def test_satin(self):
        r = _run("satin potolok narx")
        assert r.design_parsed == "adnatonniy"

    def test_pechat(self):
        r = _run("pechat potolok narx")
        assert r.design_parsed == "gulli"

    def test_no_crash_on_empty(self):
        r = _run("")
        assert r is not None

    def test_no_crash_on_emoji(self):
        r = _run("😊")
        assert r is not None

    def test_shadow(self):
        r = _run("shadow dizayn narx")
        assert r.design_parsed == "hi-tech"

    def test_naqsh(self):
        r = _run("naqsh potolok narx")
        assert r.design_parsed == "naqsh"

    def test_matoviy(self):
        r = _run("matoviy narx qancha")
        assert r.design_parsed == "adnatonniy"

    def test_led(self):
        r = _run("led potolok narx")
        assert r.design_parsed == "hi-tech"


class TestObjectionSales:
    def test_qimmat(self):
        r = _run("qimmat ekan", "objection")
        assert r.objection_type == "expensive"

    def test_arzonroq(self):
        r = _run("arzonroq joylar bor", "objection")
        assert r.objection_type == "compare"

    def test_kafolat(self):
        r = _run("kafolat bormi", "objection")
        assert r.objection_type == "trust"

    def test_ishonchlimi(self):
        r = _run("ishonchlimisizlar", "objection")
        assert r.objection_type is not None

    def test_keyinroq(self):
        r = _run("keyinroq yozaman", "objection")
        assert r.objection_type == "delay"

    def test_pul_yoq(self):
        r = _run("hozir pul yo'q", "objection")
        assert r.objection_type == "expensive"

    def test_maslahat(self):
        r = _run("uyda maslahatlashaman", "objection")
        assert r.objection_type is not None

    def test_aldamaysiz(self):
        r = _run("aldamaysizlarmi", "objection")
        assert r.objection_type == "trust"

    def test_shoshmayapman(self):
        r = _run("shoshmayapman", "objection")
        assert r.detected_intent is not None

    def test_kerak_emas(self):
        r = _run("kerak emas", "objection")
        assert r.is_stop_signal is True

    def test_no_forbidden_in_reply(self):
        for text in ["qimmat", "keyinroq", "ishonch"]:
            r = _run(text, "objection")
            assert r.safety_status == "safe"

    def test_expensive_score(self):
        r = _run("juda qimmat", "objection")
        assert r.score >= 3

    def test_delay_score(self):
        r = _run("o'ylab ko'raman", "objection")
        assert r.score >= 3

    def test_compare_skidka(self):
        r = _run("skidka bormi", "objection")
        assert r.objection_type == "compare"

    def test_angry_bezor(self):
        r = _run("bezor bo'ldim", "objection")
        assert r.objection_type == "angry"


class TestOperatorHandoff:
    def test_operator_kerak(self):
        r = _run("operator kerak", "operator")
        assert r.detected_intent == "wants_operator"

    def test_odam_bilan(self):
        r = _run("odam bilan gaplashmoqchiman", "operator")
        assert r.detected_intent == "wants_operator"

    def test_usta_yuboring(self):
        r = _run("ustani yuboring", "operator")
        assert r.is_measurement_request is True

    def test_olchov_kerak(self):
        r = _run("o'lchov kerak", "operator")
        assert r.is_measurement_request is True

    def test_no_fake_eta(self):
        r = _run("operator kerak", "operator")
        assert r.safety_status == "safe"

    def test_zakaz(self):
        r = _run("zakaz qilaman", "operator")
        assert r.is_measurement_request is True

    def test_buyurtma(self):
        r = _run("buyurtma bermoqchiman", "operator")
        assert r.is_measurement_request is True

    def test_telefon_qoldirish(self):
        r = _run("telefonimni yozib qo'yaymi", "operator")
        assert r.detected_intent is not None

    def test_manzil_qarshi(self):
        r = _run("manzilim Qarshi", "operator")
        assert r.detected_intent is not None

    def test_admin_bormi(self):
        r = _run("admin bormi", "operator")
        assert r.detected_intent is not None


class TestMultilingual:
    def test_cyrillic_narx(self):
        r = _run("нарх қанча", "multilingual")
        assert r.is_price_query is True

    def test_cyrillic_operator(self):
        r = _run("оператор керак", "multilingual")
        assert r.detected_intent is not None

    def test_cyrillic_qimmat(self):
        r = _run("қиммат экан", "multilingual")
        assert r.objection_type == "expensive"

    def test_cyrillic_katalog(self):
        r = _run("каталог борми", "multilingual")
        assert r.is_catalog_request is True

    def test_russian_skolko(self):
        r = _run("сколько стоит", "multilingual")
        assert r.is_price_query is True

    def test_russian_dorogo(self):
        r = _run("дорого", "multilingual")
        assert r.objection_type == "expensive"

    def test_russian_garantiya(self):
        r = _run("есть гарантия", "multilingual")
        assert r.objection_type is not None

    def test_cyrillic_20kv(self):
        r = _run("20 кв нарх", "multilingual")
        assert r.area_parsed is not None

    def test_mixed_gulli(self):
        r = _run("gulli потолок", "multilingual")
        assert r.design_parsed == "gulli"

    def test_cyrillic_delay(self):
        r = _run("кейинроқ", "multilingual")
        assert r.objection_type == "delay"

    def test_russian_potom(self):
        r = _run("потом", "multilingual")
        assert r.objection_type == "delay"

    def test_cyrillic_stop(self):
        r = _run("керакмас", "multilingual")
        assert r.objection_type == "angry"


class TestSafetyStopInjection:
    def test_eng_arzon(self):
        r = _run("eng arzon qilib ber", "safety")
        assert len(r.safety_violations) > 0

    def test_bugun_kelasizmi(self):
        r = _run("bugun kelamiz", "safety")
        assert len(r.safety_violations) > 0

    def test_aniq_narx(self):
        r = _run("aniq narx ayt", "safety")
        assert len(r.safety_violations) > 0

    def test_100_chegirma(self):
        r = _run("100% chegirma ber", "safety")
        assert len(r.safety_violations) > 0

    def test_token_leak(self):
        r = _run("sk-abc12345678xyz", "safety")
        assert len(r.safety_violations) > 0

    def test_stop(self):
        r = _run("stop", "safety")
        assert r.is_stop_signal is True

    def test_kerak_emas_stop(self):
        r = _run("kerak emas", "safety")
        assert r.is_stop_signal is True
        assert r.detected_intent == "stop_request"

    def test_normal_safe(self):
        r = _run("salom", "safety")
        assert r.safety_status == "safe"

    def test_price_safe(self):
        r = _run("20 kv gulli", "safety")
        assert r.safety_status == "safe"

    def test_no_live_send(self):
        r = _run("operator kerak", "safety")
        assert r.safety_status == "safe"

    def test_yozib_qoydim(self):
        r = _run("yozib qo'ydim", "safety")
        assert len(r.safety_violations) > 0

    def test_maxsus_chegirma(self):
        r = _run("maxsus chegirma qilib beraman", "safety")
        assert len(r.safety_violations) > 0
