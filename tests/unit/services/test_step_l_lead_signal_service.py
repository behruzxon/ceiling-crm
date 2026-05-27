"""Tests for Step L — LeadSignalService (lead scoring 2.0 + objection detection)."""
from __future__ import annotations

import pytest

from core.services.lead_signal_service import LeadSignalService
from shared.constants.enums import CustomerIntent, ObjectionType, UrgencyLevel

# ─── Helpers ──────────────────────────────────────────────────────────────────

svc = LeadSignalService


# ─── 1. Intent detection — Uzbek ─────────────────────────────────────────────


class TestDetectIntent:
    def test_narxi_qancha_wants_price(self):
        assert svc.detect_intent("narxi qancha") == CustomerIntent.WANTS_PRICE

    def test_hisobla_wants_price(self):
        assert svc.detect_intent("hisoblab bering") == CustomerIntent.WANTS_PRICE

    def test_20_kv_wants_price(self):
        assert svc.detect_intent("20 kv hisobla") == CustomerIntent.WANTS_PRICE

    def test_m2_wants_price(self):
        assert svc.detect_intent("30 m2 narxi") == CustomerIntent.WANTS_PRICE

    def test_katalog_bormi_wants_catalog(self):
        assert svc.detect_intent("katalog bormi") == CustomerIntent.WANTS_CATALOG

    def test_dizayn_wants_catalog(self):
        assert svc.detect_intent("dizayn ko'rsating") == CustomerIntent.WANTS_CATALOG

    def test_rasm_wants_catalog(self):
        assert svc.detect_intent("rasm bor") == CustomerIntent.WANTS_CATALOG

    def test_zakaz_bermoqchiman_wants_order(self):
        assert svc.detect_intent("zakaz bermoqchiman") == CustomerIntent.WANTS_ORDER

    def test_buyurtma_wants_order(self):
        assert svc.detect_intent("buyurtma qilaman") == CustomerIntent.WANTS_ORDER

    def test_operator_boglansin_wants_operator(self):
        assert svc.detect_intent("operator bog'lansin") == CustomerIntent.WANTS_OPERATOR

    def test_odam_bilan_wants_operator(self):
        assert svc.detect_intent("odam bilan gaplashaman") == CustomerIntent.WANTS_OPERATOR

    def test_usta_wants_measurement(self):
        assert svc.detect_intent("usta chaqiring") == CustomerIntent.WANTS_MEASUREMENT

    def test_olchovchi_wants_measurement(self):
        assert svc.detect_intent("o'lchovchi kerak") == CustomerIntent.WANTS_MEASUREMENT

    def test_chegirma_bormi_wants_discount(self):
        assert svc.detect_intent("chegirma bormi") == CustomerIntent.WANTS_DISCOUNT

    def test_skidka_wants_discount(self):
        assert svc.detect_intent("skidka bormi") == CustomerIntent.WANTS_DISCOUNT

    def test_kerak_emas_stop_request(self):
        assert svc.detect_intent("kerak emas") == CustomerIntent.STOP_REQUEST

    def test_kerakmas_stop_request(self):
        assert svc.detect_intent("kerakmas") == CustomerIntent.STOP_REQUEST

    def test_yozmang_stop_request(self):
        assert svc.detect_intent("yozmang") == CustomerIntent.STOP_REQUEST

    def test_stop_stop_request(self):
        assert svc.detect_intent("stop") == CustomerIntent.STOP_REQUEST

    def test_qiziqmayman_stop_request(self):
        assert svc.detect_intent("qiziqmayman") == CustomerIntent.STOP_REQUEST

    def test_empty_text_unclear(self):
        assert svc.detect_intent("") == CustomerIntent.UNCLEAR

    def test_generic_text_unclear(self):
        assert svc.detect_intent("salom") == CustomerIntent.UNCLEAR

    def test_kerak_weak_order(self):
        assert svc.detect_intent("potolok kerak") == CustomerIntent.WANTS_ORDER

    def test_boshlaymiz_weak_order(self):
        assert svc.detect_intent("boshlaymiz") == CustomerIntent.WANTS_ORDER


# ─── 2. Intent detection — Russian ──────────────────────────────────────────


class TestDetectIntentRussian:
    def test_skolko_stoit_wants_price(self):
        assert svc.detect_intent("сколько стоит") == CustomerIntent.WANTS_PRICE

    def test_tsena_wants_price(self):
        assert svc.detect_intent("какая цена") == CustomerIntent.WANTS_PRICE

    def test_pozvanite_wants_operator(self):
        assert svc.detect_intent("позвоните мне") == CustomerIntent.WANTS_OPERATOR

    def test_zakazat_wants_order(self):
        assert svc.detect_intent("хочу заказать") == CustomerIntent.WANTS_ORDER

    def test_katalog_ru_wants_catalog(self):
        assert svc.detect_intent("покажите каталог") == CustomerIntent.WANTS_CATALOG

    def test_ne_nado_stop(self):
        assert svc.detect_intent("не надо") == CustomerIntent.STOP_REQUEST

    def test_stop_ru(self):
        assert svc.detect_intent("стоп") == CustomerIntent.STOP_REQUEST

    def test_otmena_stop(self):
        assert svc.detect_intent("отмена") == CustomerIntent.STOP_REQUEST

    def test_zamer_wants_measurement(self):
        assert svc.detect_intent("замер нужен") == CustomerIntent.WANTS_MEASUREMENT

    def test_skidka_ru_wants_discount(self):
        assert svc.detect_intent("есть скидка?") == CustomerIntent.WANTS_DISCOUNT


# ─── 3. Objection detection ─────────────────────────────────────────────────


class TestDetectObjection:
    def test_qimmat_ekan_price(self):
        assert svc.detect_objection("qimmat ekan") == ObjectionType.PRICE

    def test_qimmatku_price(self):
        assert svc.detect_objection("qimmatku") == ObjectionType.PRICE

    def test_pulim_yetmaydi_price(self):
        assert svc.detect_objection("pulim yetmaydi") == ObjectionType.PRICE

    def test_dorogo_price(self):
        assert svc.detect_objection("дорого") == ObjectionType.PRICE

    def test_kafolat_trust(self):
        assert svc.detect_objection("kafolat bormi") == ObjectionType.TRUST

    def test_garantiya_trust(self):
        assert svc.detect_objection("гарантия есть?") == ObjectionType.TRUST

    def test_ishonch_trust(self):
        assert svc.detect_objection("ishonch yo'q") == ObjectionType.TRUST

    def test_keyinroq_not_ready(self):
        assert svc.detect_objection("keyinroq") == ObjectionType.NOT_READY

    def test_hali_emas_not_ready(self):
        assert svc.detect_objection("hali emas") == ObjectionType.NOT_READY

    def test_pozje_not_ready(self):
        assert svc.detect_objection("позже") == ObjectionType.NOT_READY

    def test_boshqa_firma_comparing(self):
        assert svc.detect_objection("boshqa firma bilan taqqoslayapman") == ObjectionType.COMPARING

    def test_konkurrent_comparing(self):
        assert svc.detect_objection("конкурент") == ObjectionType.COMPARING

    def test_oylab_koraman_consultation(self):
        assert svc.detect_objection("o'ylab ko'raman") == ObjectionType.NEED_CONSULTATION

    def test_podumayu_consultation(self):
        assert svc.detect_objection("подумаю") == ObjectionType.NEED_CONSULTATION

    def test_erim_bilan_family(self):
        assert svc.detect_objection("erim bilan maslahat qilaman") == ObjectionType.SPOUSE_FAMILY_DECISION

    def test_s_muzhem_family(self):
        assert svc.detect_objection("с мужем посоветуюсь") == ObjectionType.SPOUSE_FAMILY_DECISION

    def test_no_objection(self):
        assert svc.detect_objection("salom") is None

    def test_uzoq_joy_location(self):
        assert svc.detect_objection("uzoq joy bizdan") == ObjectionType.LOCATION


# ─── 4. Urgency detection ───────────────────────────────────────────────────


class TestDetectUrgency:
    def test_bugun_high(self):
        assert svc.detect_urgency("bugun kerak") == UrgencyLevel.HIGH

    def test_ertaga_high(self):
        assert svc.detect_urgency("ertaga kerak") == UrgencyLevel.HIGH

    def test_tez_high(self):
        assert svc.detect_urgency("tez qiling") == UrgencyLevel.HIGH

    def test_shoshilinch_high(self):
        assert svc.detect_urgency("shoshilinch") == UrgencyLevel.HIGH

    def test_shu_hafta_high(self):
        assert svc.detect_urgency("shu hafta qilsangiz") == UrgencyLevel.HIGH

    def test_segodnya_high(self):
        assert svc.detect_urgency("сегодня нужно") == UrgencyLevel.HIGH

    def test_zavtra_high(self):
        assert svc.detect_urgency("завтра можно?") == UrgencyLevel.HIGH

    def test_srochno_high(self):
        assert svc.detect_urgency("срочно") == UrgencyLevel.HIGH

    def test_shu_oyda_medium(self):
        assert svc.detect_urgency("shu oyda qilsak") == UrgencyLevel.MEDIUM

    def test_yaqinda_medium(self):
        assert svc.detect_urgency("yaqinda") == UrgencyLevel.MEDIUM

    def test_no_urgency_low(self):
        assert svc.detect_urgency("salom") == UrgencyLevel.LOW


# ─── 5. Area detection ──────────────────────────────────────────────────────


class TestDetectArea:
    def test_5x4_area(self):
        assert svc.detect_area_mention("5x4 xona") == 20.0

    def test_20_kv_area(self):
        assert svc.detect_area_mention("20 kv") == 20.0

    def test_30_m2_area(self):
        assert svc.detect_area_mention("30 m2") == 30.0

    def test_no_area(self):
        assert svc.detect_area_mention("salom") is None


# ─── 6. Budget detection ────────────────────────────────────────────────────


class TestDetectBudget:
    def test_10_mln(self):
        assert svc.detect_budget_mention("10 mln") == 10_000_000

    def test_5_million(self):
        assert svc.detect_budget_mention("5 million so'm") == 5_000_000

    def test_500_ming(self):
        assert svc.detect_budget_mention("500 ming") == 500_000

    def test_15_mln_ru(self):
        assert svc.detect_budget_mention("15 млн") == 15_000_000

    def test_no_budget(self):
        assert svc.detect_budget_mention("salom") is None


# ─── 7. extract_signals integration ─────────────────────────────────────────


class TestExtractSignals:
    def test_narxi_qancha_full_signal(self):
        r = svc.extract_signals("narxi qancha")
        assert r.intent == "wants_price"
        assert r.objection_type is None
        assert r.urgency == "low"
        assert r.area_m2 is None
        assert r.should_disable_followup is False

    def test_20_kv_hisobla_price_with_area(self):
        r = svc.extract_signals("20 kv hisobla")
        assert r.intent == "wants_price"
        assert r.area_m2 == 20.0
        assert r.lead_score_delta > 15

    def test_5x4_area_extraction(self):
        r = svc.extract_signals("5x4 xona uchun")
        assert r.area_m2 == 20.0

    def test_kerak_emas_stop(self):
        r = svc.extract_signals("kerak emas")
        assert r.intent == "stop_request"
        assert r.should_disable_followup is True
        assert r.lead_score_delta == 0

    def test_qimmat_sends_objection(self):
        r = svc.extract_signals("qimmat ekan")
        assert r.objection_type == "price"
        assert r.intent == "sends_objection"

    def test_russian_language_detected(self):
        r = svc.extract_signals("сколько стоит потолок")
        assert r.language == "ru"
        assert r.intent == "wants_price"

    def test_uzbek_language_default(self):
        r = svc.extract_signals("narxi qancha")
        assert r.language == "uz"

    def test_language_hint_override(self):
        r = svc.extract_signals("narxi qancha", language_hint="ru")
        assert r.language == "ru"

    def test_high_urgency_notifies_admin(self):
        r = svc.extract_signals("bugun kerak, narxini ayting")
        assert r.urgency == "high"
        assert r.should_notify_admin is True

    def test_order_notifies_admin(self):
        r = svc.extract_signals("zakaz beraman")
        assert r.should_notify_admin is True

    def test_operator_notifies_admin(self):
        r = svc.extract_signals("operator chaqiring")
        assert r.should_notify_admin is True

    def test_mixed_narx_qimmat(self):
        r = svc.extract_signals("narxi qimmat ekan")
        assert r.intent == "wants_price"
        assert r.objection_type == "price"

    def test_budget_10mln(self):
        r = svc.extract_signals("budjetim 10 mln")
        assert r.budget_amount == 10_000_000

    def test_confidence_increases_with_more_signals(self):
        simple = svc.extract_signals("salom")
        rich = svc.extract_signals("bugun 20 m2 narx hisobla")
        assert rich.confidence_score > simple.confidence_score

    def test_ertaga_kerak_urgency_and_order(self):
        r = svc.extract_signals("ertaga kerak")
        assert r.urgency == "high"


# ─── 8. Score calculation ───────────────────────────────────────────────────


class TestCalculateLeadScore:
    def test_stop_returns_zero(self):
        sig = svc.extract_signals("kerak emas")
        score = svc.calculate_lead_score({}, [], sig)
        assert score == 0

    def test_price_only_warm_range(self):
        sig = svc.extract_signals("narxi qancha")
        score = svc.calculate_lead_score({}, [], sig)
        assert 10 <= score <= 50

    def test_order_area_urgency_hot(self):
        sig = svc.extract_signals("bugun 20 m2 zakaz qilaman")
        score = svc.calculate_lead_score({}, [], sig)
        assert score >= 70

    def test_existing_score_adds(self):
        sig = svc.extract_signals("narxi qancha")
        score = svc.calculate_lead_score({"lead_score": 40}, [], sig)
        assert score > 40

    def test_events_boost_score(self):
        sig = svc.extract_signals("salom")
        events = [{"event_type": "phone_shared"}]
        score = svc.calculate_lead_score({}, events, sig)
        assert score >= 40

    def test_score_clamped_100(self):
        sig = svc.extract_signals("bugun zakaz qilaman 50 m2")
        score = svc.calculate_lead_score({"lead_score": 90}, [
            {"event_type": "phone_shared"},
            {"event_type": "operator_requested"},
        ], sig)
        assert score <= 100

    def test_score_clamped_0(self):
        sig = svc.extract_signals("kerak emas")
        score = svc.calculate_lead_score({"lead_score": 50}, [], sig)
        assert score == 0


# ─── 9. Temperature classification ──────────────────────────────────────────


class TestClassifyTemperature:
    def test_hot_70(self):
        assert svc.classify_temperature(70) == "hot"

    def test_hot_100(self):
        assert svc.classify_temperature(100) == "hot"

    def test_warm_50(self):
        assert svc.classify_temperature(50) == "warm"

    def test_warm_31(self):
        assert svc.classify_temperature(31) == "warm"

    def test_cold_30(self):
        assert svc.classify_temperature(30) == "cold"

    def test_cold_0(self):
        assert svc.classify_temperature(0) == "cold"


# ─── 10. Memory update ──────────────────────────────────────────────────────


class TestUpdateMemoryFromSignal:
    def test_basic_update(self):
        sig = svc.extract_signals("narxi qancha")
        md = svc.update_memory_from_signal({}, sig)
        assert md["last_intent"] == "wants_price"
        assert md["urgency"] == "low"

    def test_area_update(self):
        sig = svc.extract_signals("20 m2 potolok")
        md = svc.update_memory_from_signal({}, sig)
        assert md["area_m2"] == 20.0

    def test_budget_update(self):
        sig = svc.extract_signals("budjetim 10 mln")
        md = svc.update_memory_from_signal({}, sig)
        assert md["budget_amount"] == 10_000_000

    def test_stop_sets_disable_flag(self):
        sig = svc.extract_signals("kerak emas")
        md = svc.update_memory_from_signal({}, sig)
        assert md["should_disable_followup"] is True

    def test_objection_preserved(self):
        sig = svc.extract_signals("qimmat ekan")
        md = svc.update_memory_from_signal({}, sig)
        assert md["objection_type"] == "price"

    def test_no_objection_preserves_existing(self):
        sig = svc.extract_signals("salom")
        md = svc.update_memory_from_signal({"objection_type": "price"}, sig)
        assert md["objection_type"] == "price"

    def test_does_not_overwrite_area_when_none(self):
        sig = svc.extract_signals("salom")
        md = svc.update_memory_from_signal({"area_m2": 30.0}, sig)
        assert md["area_m2"] == 30.0


# ─── 11. Decision engine integration ────────────────────────────────────────


class TestDecisionEngineSignals:
    def test_price_objection_negotiating(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "memory_data": {"objection_type": "price"},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "negotiating_price"

    def test_wants_operator_handoff(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "memory_data": {"last_intent": "wants_operator"},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "operator_handoff"

    def test_wants_order_intent(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "memory_data": {"last_intent": "wants_order"},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "order_intent"

    def test_wants_price_no_area_checking(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "memory_data": {"last_intent": "wants_price"},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "price_checking"

    def test_wants_price_with_area_considering(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "area_m2": 20.0,
            "memory_data": {"last_intent": "wants_price"},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "price_considering"

    def test_wants_price_with_area_in_md(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "memory_data": {"last_intent": "wants_price", "area_m2": 25.0},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "price_considering"

    def test_stop_request_stopped(self):
        from core.services.agent_decision_engine import classify_customer_state
        memory = {
            "followup_enabled": True,
            "memory_data": {"last_intent": "stop_request"},
        }
        state = classify_customer_state(memory, frozenset())
        assert state.value == "stopped"

    def test_urgency_high_priority_boost(self):
        from core.services.agent_decision_engine import calculate_priority_score
        memory_no_urgency = {
            "lead_temperature": "warm",
            "memory_data": {},
        }
        memory_with_urgency = {
            "lead_temperature": "warm",
            "memory_data": {"urgency": "high"},
        }
        score_no = calculate_priority_score(memory_no_urgency, frozenset(), 50)
        score_yes = calculate_priority_score(memory_with_urgency, frozenset(), 50)
        assert score_yes > score_no

    def test_urgency_cold_no_boost(self):
        from core.services.agent_decision_engine import calculate_priority_score
        memory = {
            "lead_temperature": "cold",
            "memory_data": {"urgency": "high"},
        }
        score = calculate_priority_score(memory, frozenset(), 50)
        memory_no = {
            "lead_temperature": "cold",
            "memory_data": {},
        }
        score_no = calculate_priority_score(memory_no, frozenset(), 50)
        assert score == score_no

    def test_event_based_still_works(self):
        from core.services.agent_decision_engine import classify_customer_state
        from shared.constants.enums import JourneyEventType
        memory = {"followup_enabled": True}
        et = frozenset({JourneyEventType.PHONE_SHARED.value})
        state = classify_customer_state(memory, et)
        assert state.value == "phone_shared_hot"


# ─── 12. Schema immutability ────────────────────────────────────────────────


class TestLeadSignalResult:
    def test_frozen(self):
        r = svc.extract_signals("narxi qancha")
        with pytest.raises(AttributeError):
            r.intent = "other"  # type: ignore[misc]

    def test_default_metadata(self):
        r = svc.extract_signals("test")
        assert r.metadata == {}
