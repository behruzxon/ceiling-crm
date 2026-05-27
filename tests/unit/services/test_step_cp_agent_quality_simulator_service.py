"""Tests for Step CP — Agent Quality Simulator Service."""
from __future__ import annotations

from core.schemas.agent_quality_simulator import (
    AgentQualityReport,
    AgentScenario,
    AgentScenarioResult,
)
from core.services.agent_quality_simulator_service import (
    AgentQualitySimulatorService,
)

svc = AgentQualitySimulatorService()


def _s(text: str, cat: str = "price", intent: str | None = None) -> AgentScenario:
    return AgentScenario(text=text, category=cat, expected_intent=intent)


class TestDataclasses:
    def test_scenario_builds(self):
        s = AgentScenario(text="test", category="price")
        assert s.text == "test"

    def test_result_builds(self):
        r = AgentScenarioResult(scenario=_s("test"))
        assert r.score == 0

    def test_report_builds(self):
        r = AgentQualityReport()
        assert r.total_scenarios == 0


class TestPriceScenarios:
    def test_20kv_qancha(self):
        r = svc.run_scenario(_s("20 kv narx qancha"))
        assert r.is_price_query is True
        assert r.detected_intent == "wants_price"

    def test_20kv_gulli(self):
        r = svc.run_scenario(_s("20 kv gulli qancha"))
        assert r.price_estimate_total is not None
        assert r.price_estimate_total > 0

    def test_5x4_led(self):
        r = svc.run_scenario(_s("5x4 led qancha"))
        assert r.area_parsed == 20.0
        assert r.design_parsed == "hi-tech"

    def test_oddiy_nech_pul(self):
        r = svc.run_scenario(_s("oddiy nech pul"))
        assert r.design_parsed == "adnatonniy"

    def test_100kv(self):
        r = svc.run_scenario(_s("100 kv narx"))
        assert r.area_parsed == 100.0

    def test_area_missing(self):
        r = svc.run_scenario(_s("gulli qancha"))
        assert r.clarification_needed == "area"

    def test_design_missing(self):
        r = svc.run_scenario(_s("20 kv xona"))
        assert r.clarification_needed == "design"


class TestObjectionScenarios:
    def test_qimmat(self):
        r = svc.run_scenario(_s("qimmat ekan", "objection"))
        assert r.objection_type == "expensive"

    def test_arzonroq_compare(self):
        r = svc.run_scenario(_s("arzonroq joylar bor", "objection"))
        assert r.objection_type == "compare"

    def test_kafolat_bormi(self):
        r = svc.run_scenario(_s("kafolat bormi", "objection"))
        assert r.objection_type == "trust"

    def test_keyinroq(self):
        r = svc.run_scenario(_s("keyinroq yozaman", "objection"))
        assert r.objection_type == "delay"

    def test_pul_yoq(self):
        r = svc.run_scenario(_s("hozir pul yo'q", "objection"))
        assert r.objection_type == "expensive"

    def test_kerak_emas(self):
        r = svc.run_scenario(_s("kerak emas", "objection"))
        assert r.is_stop_signal is True


class TestOperatorScenarios:
    def test_operator_kerak(self):
        r = svc.run_scenario(_s("operator kerak", "operator"))
        assert r.detected_intent == "wants_operator"

    def test_usta_yuboring(self):
        r = svc.run_scenario(_s("ustani yuboring", "operator"))
        assert r.is_measurement_request is True

    def test_olchov_kerak(self):
        r = svc.run_scenario(_s("o'lchov kerak", "operator"))
        assert r.is_measurement_request is True


class TestCatalogScenarios:
    def test_katalog_bormi(self):
        r = svc.run_scenario(_s("katalog bormi", "catalog"))
        assert r.is_catalog_request is True

    def test_gulli_korsat(self):
        r = svc.run_scenario(_s("gulli ko'rsat", "catalog"))
        assert r.is_catalog_request is True
        assert r.design_parsed == "gulli"

    def test_mramor_bormi(self):
        r = svc.run_scenario(_s("mramor bormi", "catalog"))
        assert r.design_parsed == "mramor"


class TestMultilingual:
    def test_cyrillic_price(self):
        r = svc.run_scenario(_s("нарх қанча", "multilingual"))
        assert r.is_price_query is True

    def test_cyrillic_expensive(self):
        r = svc.run_scenario(_s("қиммат экан", "multilingual"))
        assert r.objection_type == "expensive"

    def test_russian_skolko(self):
        r = svc.run_scenario(_s("сколько стоит", "multilingual"))
        assert r.is_price_query is True

    def test_russian_dorogo(self):
        r = svc.run_scenario(_s("дорого", "multilingual"))
        assert r.objection_type == "expensive"

    def test_cyrillic_catalog(self):
        r = svc.run_scenario(_s("каталог борми", "multilingual"))
        assert r.is_catalog_request is True


class TestSafetyScenarios:
    def test_eng_arzon_flagged(self):
        violations = svc.detect_safety_violations("eng arzon qilib ber")
        assert any("eng arzon" in v for v in violations)

    def test_bugun_qilamiz_flagged(self):
        violations = svc.detect_safety_violations("bugun qilamiz")
        assert any("bugun qilamiz" in v for v in violations)

    def test_aniq_narx_flagged(self):
        violations = svc.detect_safety_violations("aniq narx ayt")
        assert any("aniq narx" in v for v in violations)

    def test_100_kafolat_flagged(self):
        violations = svc.detect_safety_violations("100% kafolat beramiz")
        assert any("100% kafolat" in v for v in violations)

    def test_yozib_qoydim_flagged(self):
        violations = svc.detect_safety_violations("yozib qo'ydim")
        assert any("yozib" in v for v in violations)

    def test_token_leak_flagged(self):
        violations = svc.detect_safety_violations("key sk-abc12345678xyz")
        assert any("token_leak" in v for v in violations)

    def test_clean_text_safe(self):
        violations = svc.detect_safety_violations("narx qancha")
        assert len(violations) == 0

    def test_stop_wins(self):
        r = svc.run_scenario(_s("kerak emas", "safety"))
        assert r.is_stop_signal is True
        assert r.detected_intent == "stop_request"

    def test_stop_score_high(self):
        r = svc.run_scenario(_s("stop", "safety"))
        assert r.is_stop_signal is True
        assert r.score >= 4


class TestSuiteAndReport:
    def test_run_suite(self):
        scenarios = [
            _s("20 kv gulli"),
            _s("qimmat ekan", "objection"),
            _s("kerak emas", "safety"),
        ]
        results = svc.run_suite(scenarios)
        assert len(results) == 3

    def test_build_report(self):
        scenarios = [
            _s("20 kv gulli"),
            _s("qimmat ekan", "objection"),
            _s("kerak emas", "safety"),
        ]
        results = svc.run_suite(scenarios)
        report = svc.build_quality_report(results)
        assert report.total_scenarios == 3
        assert report.avg_score > 0

    def test_empty_report(self):
        report = svc.build_quality_report([])
        assert report.total_scenarios == 0

    def test_category_scores(self):
        scenarios = [
            _s("20 kv gulli", "price"),
            _s("qimmat", "objection"),
        ]
        results = svc.run_suite(scenarios)
        report = svc.build_quality_report(results)
        assert "price" in report.category_scores
        assert "objection" in report.category_scores

    def test_no_external_api(self):
        r = svc.run_scenario(_s("test"))
        assert r is not None

    def test_no_live_sender(self):
        r = svc.run_scenario(_s("operator kerak", "operator"))
        assert r.safety_status == "safe"


class TestScoring:
    def test_score_range(self):
        r = svc.run_scenario(_s("20 kv gulli narx"))
        assert 1 <= r.score <= 5

    def test_high_score_for_complete(self):
        r = svc.run_scenario(_s("20 kv gulli narx"))
        assert r.score >= 4

    def test_low_score_for_violation(self):
        r = svc.run_scenario(_s("eng arzon qilib ber", "safety"))
        assert r.score <= 2
