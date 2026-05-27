"""
Agent Simulation Lab — 80+ scenario-based tests.

Runs virtual customer messages and events through the full agent pipeline
(signal → decision → offer → policy → orchestrator) without any real bot
interaction, OpenAI calls, or database access.
"""

from __future__ import annotations

from tests.simulation.agent.simulation_runner import build_memory, run_scenario

# ═══════════════════════════════════════════════════════════════════════════════
# A) Direct price scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestPriceScenarios:
    def test_a01_narxi_qancha(self):
        r = run_scenario("narxi qancha", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"
        assert r.offer_type == "price_calculation"
        assert r.orch_action == "send_user_reply"

    def test_a02_20_kv_qancha(self):
        r = run_scenario("20 kv qancha", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"
        assert r.signal_area == 20.0
        assert r.offer_type == "price_calculation"
        assert "turini" in (r.orch_user_text or "").lower()

    def test_a03_5x4_xona_hisobla(self):
        r = run_scenario("5x4 xona hisobla", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"
        assert r.signal_area == 20.0

    def test_a04_30m2_gulli_qancha(self):
        r = run_scenario("30 m2 gulli qancha", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"
        assert r.signal_area == 30.0


# ═══════════════════════════════════════════════════════════════════════════════
# B) Catalog / design scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestCatalogScenarios:
    def test_b05_katalog_bormi(self):
        r = run_scenario("katalog bormi", build_memory(temp="warm"))
        assert r.signal_intent == "wants_catalog"
        assert r.orch_action == "send_user_reply"

    def test_b06_gulli_potalok(self):
        r = run_scenario("gulli potalok bormi", build_memory(temp="warm"))
        assert r.signal_intent == "wants_catalog"

    def test_b07_matoviy_rasm(self):
        r = run_scenario("matoviy rasm tashlang", build_memory(temp="warm"))
        assert r.signal_intent == "wants_catalog"

    def test_b08_catalog_no_admin_escalation(self):
        r = run_scenario("katalog bormi", build_memory(temp="warm"))
        assert r.orch_admin_text is None


# ═══════════════════════════════════════════════════════════════════════════════
# C) Order intent scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrderScenarios:
    def test_c09_zakaz_bermoqchiman(self):
        r = run_scenario("zakaz bermoqchiman", build_memory(temp="warm"))
        assert r.signal_intent == "wants_order"
        assert r.offer_type == "order_continue"
        assert r.orch_action == "send_user_reply"

    def test_c10_ustani_chaqiraylik(self):
        r = run_scenario("ustani chaqiraylik", build_memory(temp="warm"))
        assert r.signal_intent == "wants_measurement"

    def test_c11_qilamiz(self):
        r = run_scenario("qilamiz", build_memory(temp="warm"))
        assert r.signal_intent == "wants_order"

    def test_c12_order_abandoned_followup(self):
        r = run_scenario(
            memory=build_memory(state="order_abandoned", temp="warm"),
        )
        assert r.policy_action in ("schedule_followup", "wait_and_observe", "store_only")


# ═══════════════════════════════════════════════════════════════════════════════
# D) Operator scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestOperatorScenarios:
    def test_d13_operator_kerak(self):
        r = run_scenario("operator kerak", build_memory(temp="warm"))
        assert r.signal_intent == "wants_operator"
        assert r.orch_action in ("handoff_operator", "send_user_reply")
        assert r.orch_cancel_pending is True

    def test_d14_telefon_qiling(self):
        r = run_scenario("telefon qiling", build_memory(temp="warm"))
        assert r.signal_intent == "wants_operator"

    def test_d15_odam_bilan(self):
        r = run_scenario("odam bilan gaplashaman", build_memory(temp="warm"))
        assert r.signal_intent == "wants_operator"
        assert r.orch_cancel_pending is True


# ═══════════════════════════════════════════════════════════════════════════════
# E) Price objection scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestPriceObjectionScenarios:
    def test_e16_qimmat_ekan(self):
        r = run_scenario("qimmat ekan", build_memory(temp="warm"))
        assert r.signal_objection == "price"
        assert r.offer_type == "cheaper_option"
        assert r.orch_action == "send_user_reply"

    def test_e17_arzonroq_bormi(self):
        r = run_scenario("arzonroq bormi", build_memory(temp="warm"))
        assert r.signal_intent == "wants_discount"

    def test_e18_pulim_yetmaydi(self):
        r = run_scenario("pulim yetmaydi", build_memory(temp="warm"))
        assert r.signal_objection == "price"

    def test_e19_dorogo_ru(self):
        r = run_scenario("дорого", build_memory(temp="warm"))
        assert r.signal_objection == "price"
        assert r.offer_type == "cheaper_option"

    def test_e_no_eng_arzon_in_reply(self):
        r = run_scenario("qimmat ekan", build_memory(temp="warm"))
        if r.orch_user_text:
            assert "eng arzon" not in r.orch_user_text.lower()

    def test_e_no_fake_discount(self):
        r = run_scenario("qimmat ekan", build_memory(temp="warm"))
        if r.orch_user_text:
            assert "10%" not in r.orch_user_text
            assert "20%" not in r.orch_user_text


# ═══════════════════════════════════════════════════════════════════════════════
# F) Trust objection scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrustObjectionScenarios:
    def test_f20_kafolat_bormi(self):
        r = run_scenario("kafolat bormi", build_memory(temp="warm"))
        assert r.signal_objection == "trust"
        assert r.offer_type in ("warranty_trust", "portfolio_social_proof")

    def test_f21_ishlaringiz(self):
        r = run_scenario("oldin ishlaringiz qanday", build_memory(temp="warm"))
        assert r.signal_objection == "trust"

    def test_f22_real_rasm(self):
        r = run_scenario("real rasm bormi", build_memory(temp="warm"))
        assert r.signal_objection == "trust"

    def test_f23_garantiya_ru(self):
        r = run_scenario("гарантия есть?", build_memory(temp="warm"))
        assert r.signal_objection == "trust"


# ═══════════════════════════════════════════════════════════════════════════════
# G) Not ready scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotReadyScenarios:
    def test_g24_keyinroq(self):
        r = run_scenario("keyinroq", build_memory(temp="warm"))
        assert r.signal_objection == "not_ready"
        assert r.policy_action in ("wait_and_observe", "schedule_followup")

    def test_g25_oylab_koraman(self):
        r = run_scenario("o'ylab ko'raman", build_memory(temp="warm"))
        assert r.signal_objection == "need_consultation"

    def test_g26_hali_aniq_emas(self):
        r = run_scenario("hali emas", build_memory(temp="warm"))
        assert r.signal_objection == "not_ready"

    def test_g_no_aggressive_followup(self):
        r = run_scenario("keyinroq", build_memory(temp="warm"))
        assert r.orch_action != "send_user_reply" or r.policy_action == "reply_now"


# ═══════════════════════════════════════════════════════════════════════════════
# H) Urgency scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestUrgencyScenarios:
    def test_h27_ertaga_kerak(self):
        r = run_scenario("ertaga kerak", build_memory(temp="warm"))
        assert r.signal_urgency == "high"

    def test_h28_bugun_warm_escalation(self):
        r = run_scenario("bugun qilib berasizmi", build_memory(temp="warm"))
        assert r.signal_urgency == "high"

    def test_h29_tez_kerak(self):
        r = run_scenario("tez kerak", build_memory(temp="warm"))
        assert r.signal_urgency == "high"

    def test_h30_shoshilinch(self):
        r = run_scenario("shoshilinch", build_memory(temp="warm"))
        assert r.signal_urgency == "high"

    def test_h_cold_no_admin_escalation(self):
        r = run_scenario("bugun kerak", build_memory(temp="cold"))
        assert r.orch_action != "send_admin_alert"

    def test_h_no_bugun_qilamiz_promise(self):
        r = run_scenario("bugun kerak", build_memory(temp="warm"))
        if r.orch_user_text:
            assert "bugun qilamiz" not in r.orch_user_text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# I) Stop scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestStopScenarios:
    def test_i31_kerak_emas(self):
        r = run_scenario("kerak emas", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"
        assert r.orch_action == "disable_agent"
        assert r.orch_cancel_pending is True

    def test_i32_yozmang(self):
        r = run_scenario("yozmang", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"
        assert r.orch_disable_agent is True

    def test_i33_stop(self):
        r = run_scenario("stop", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"

    def test_i34_ne_nado_ru(self):
        r = run_scenario("не надо", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"
        assert r.orch_action == "disable_agent"

    def test_i_stop_overrides_hot(self):
        r = run_scenario("kerak emas", build_memory(temp="hot", lead_score=90))
        assert r.orch_action == "disable_agent"


# ═══════════════════════════════════════════════════════════════════════════════
# J) Hot lead scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestHotLeadScenarios:
    def test_j35_phone_shared_hot(self):
        r = run_scenario(
            memory=build_memory(
                state="phone_shared_hot",
                temp="hot",
                phone=True,
            ),
        )
        assert r.policy_action == "escalate_admin"

    def test_j36_image_sent(self):
        r = run_scenario(
            memory=build_memory(temp="warm"),
            events=[{"event_type": "image_sent"}],
        )
        assert r.offer_type == "design_help"

    def test_j37_price_area_urgency_hot(self):
        r = run_scenario(
            "bugun 20 m2 narx hisobla",
            build_memory(temp="warm"),
        )
        assert r.signal_urgency == "high"
        assert r.signal_area == 20.0

    def test_j38_order_phone_hot(self):
        r = run_scenario(
            memory=build_memory(
                state="phone_shared_hot",
                temp="hot",
                phone=True,
                lead_score=80,
            ),
        )
        assert r.orch_action != "send_user_reply"

    def test_j_no_user_dm_after_phone_shared(self):
        r = run_scenario(
            "salom",
            build_memory(state="phone_shared_hot", temp="hot", phone=True),
        )
        assert r.orch_action != "send_user_reply"


# ═══════════════════════════════════════════════════════════════════════════════
# K) Cold lead / unclear
# ═══════════════════════════════════════════════════════════════════════════════


class TestColdUnclearScenarios:
    def test_k39_salom(self):
        r = run_scenario("salom", build_memory())
        assert r.signal_intent == "unclear"
        assert r.orch_action in ("store_memory_only", "no_action")

    def test_k40_ha(self):
        r = run_scenario("ha", build_memory())
        assert r.signal_intent == "unclear"

    def test_k41_emoji(self):
        r = run_scenario("😊", build_memory())
        assert r.signal_intent == "unclear"

    def test_k42_short_text(self):
        r = run_scenario("ok", build_memory())
        assert r.signal_intent == "unclear"
        assert r.orch_action in ("store_memory_only", "no_action")

    def test_k_no_sales_pressure(self):
        r = run_scenario("salom", build_memory())
        assert r.orch_action != "send_user_reply"


# ═══════════════════════════════════════════════════════════════════════════════
# L) Safety regression scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafetyRegression:
    def test_l43_lifetime_cap(self):
        r = run_scenario(
            "narxi qancha",
            build_memory(followup_count=5, temp="warm"),
        )
        assert r.orch_allowed is False

    def test_l44_daily_cap(self):
        r = run_scenario(
            "narxi qancha",
            build_memory(followup_count=3, temp="warm"),
        )
        assert r.orch_allowed is False

    def test_l45_followup_disabled(self):
        r = run_scenario(
            "narxi qancha",
            build_memory(followup_enabled=False),
        )
        assert r.orch_allowed is False

    def test_l46_deal_closed(self):
        r = run_scenario(
            memory=build_memory(state="closed", followup_enabled=False),
        )
        assert r.orch_allowed is False

    def test_l47_lost(self):
        r = run_scenario(
            memory=build_memory(state="lost", followup_enabled=False),
        )
        assert r.orch_allowed is False

    def test_l48_admin_cooldown(self):
        r = run_scenario(
            memory=build_memory(
                lead_score=80,
                temp="hot",
                admin_cooldown=True,
            ),
        )
        assert r.orch_action != "send_admin_alert" or "admin_escalation_cooldown" in r.safety_flags


# ═══════════════════════════════════════════════════════════════════════════════
# M) Multi-message journey scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestJourneyScenarios:
    def test_m49_start_catalog_price(self):
        r = run_scenario("20 kv qancha", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"
        assert r.signal_area == 20.0
        assert r.orch_action == "send_user_reply"

    def test_m50_price_then_qimmat(self):
        r = run_scenario(
            "qimmat ekan",
            build_memory(temp="warm", state="price_considering"),
        )
        assert r.signal_objection == "price"
        assert r.offer_type == "cheaper_option"

    def test_m51_catalog_then_trust(self):
        r = run_scenario(
            "kafolat bormi",
            build_memory(temp="warm", state="browsing_catalog"),
        )
        assert r.signal_objection == "trust"
        assert r.offer_type in ("warranty_trust", "portfolio_social_proof")

    def test_m52_order_no_phone_followup(self):
        r = run_scenario(
            memory=build_memory(state="order_abandoned", temp="warm"),
        )
        assert r.policy_action in ("schedule_followup", "wait_and_observe", "store_only")

    def test_m53_price_no_answer_escalation(self):
        r = run_scenario(
            memory=build_memory(
                state="price_considering",
                temp="hot",
                lead_score=75,
            ),
        )
        assert r.policy_action in ("escalate_admin", "schedule_followup", "store_only")


# ═══════════════════════════════════════════════════════════════════════════════
# N) Russian scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestRussianScenarios:
    def test_n54_skolko_stoit(self):
        r = run_scenario("сколько стоит", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"

    def test_n55_dorogo(self):
        r = run_scenario("дорого", build_memory(temp="warm"))
        assert r.signal_objection == "price"

    def test_n56_pozvanite(self):
        r = run_scenario("позвоните", build_memory(temp="warm"))
        assert r.signal_intent == "wants_operator"

    def test_n57_hochu_zakazat(self):
        r = run_scenario("хочу заказать", build_memory(temp="warm"))
        assert r.signal_intent == "wants_order"

    def test_n58_skidka_est(self):
        r = run_scenario("скидка есть", build_memory(temp="warm"))
        assert r.signal_intent == "wants_discount"


# ═══════════════════════════════════════════════════════════════════════════════
# O) Uzbek Cyrillic partial scenarios (may be unclear — TODO for Step Q)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUzbekCyrillicScenarios:
    def test_o59_narxi_qancha_cyrillic(self):
        r = run_scenario("нархи қанча", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"

    def test_o60_qimmat_cyrillic(self):
        r = run_scenario("қиммат", build_memory(temp="warm"))
        assert r.signal_objection == "price"

    def test_o61_operator_kerak_cyrillic(self):
        # "оператор" matches Russian keyword list — works already
        r = run_scenario("оператор керак", build_memory(temp="warm"))
        assert r.signal_intent == "wants_operator"


# ═══════════════════════════════════════════════════════════════════════════════
# P) AI composer safety scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestAIComposerSafety:
    def test_p62_ai_disabled_deterministic(self):
        from core.services.ai_message_composer_service import _build_user_prompt

        prompt = _build_user_prompt("catalog", {})
        assert isinstance(prompt, str)

    def test_p63_ai_composer_fallback(self):
        from core.services.ai_message_composer_service import validate_ai_output

        ok, reason = validate_ai_output("", "catalog", {})
        assert ok is False
        assert reason == "empty"

    def test_p64_offer_hint_safe(self):
        from core.services.ai_message_composer_service import _build_user_prompt

        md = {"last_dynamic_offer": {"message_hint": "Arzonroq variant bor"}}
        prompt = _build_user_prompt("price", md)
        assert "o'ylab topma" in prompt.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Q) Orchestrator trace scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestratorTrace:
    def test_q65_trace_has_all_keys(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        p = AgentResponseOrchestrator.run_pipeline(
            build_memory(temp="warm"),
            text="narxi qancha",
        )
        trace = p.debug_trace
        assert "signal" in trace
        assert "decision" in trace
        assert "offer" in trace
        assert "policy" in trace

    def test_q66_trace_redacts_phone(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        trace = AgentResponseOrchestrator.build_trace(
            signal={"phone": "+998901234567"},
            decision={},
            offer={},
            policy={},
            action="test",
            source="test",
        )
        assert "+998" not in str(trace["signal"])

    def test_q67_trace_redacts_token(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        trace = AgentResponseOrchestrator.build_trace(
            signal={"text": "sk-abc123secret"},
            decision={},
            offer={},
            policy={},
            action="test",
            source="test",
        )
        assert "sk-abc" not in str(trace["signal"])

    def test_q68_log_only_no_send(self):
        r = run_scenario("narxi qancha", build_memory(temp="warm"))
        assert r.orch_user_text is not None or r.orch_action == "store_memory_only"

    def test_q69_payload_requires_policy_allow(self):
        from core.schemas.agent_orchestrator import AgentResponsePayload
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        payload = AgentResponsePayload(
            action="send_user_reply",
            source="test",
            allowed=True,
            reason="test",
        )
        result = AgentResponseOrchestrator.apply_safety(
            payload,
            {"allowed": False},
        )
        assert result.allowed is False


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY GATES — mandatory safety checks
# ═══════════════════════════════════════════════════════════════════════════════


class TestQualityGates:
    def test_gate_stop_always_wins(self):
        for text in ("kerak emas", "stop", "не надо", "yozmang"):
            r = run_scenario(text, build_memory(temp="hot", lead_score=95))
            assert r.orch_action == "disable_agent", f"stop failed for: {text}"

    def test_gate_cold_never_escalates(self):
        r = run_scenario(
            "salom",
            build_memory(lead_score=80, temp="cold"),
        )
        assert r.orch_action != "send_admin_alert"

    def test_gate_admin_cooldown_no_dup(self):
        r = run_scenario(
            memory=build_memory(
                lead_score=80,
                temp="hot",
                admin_cooldown=True,
            ),
        )
        has_cooldown_flag = "admin_escalation_cooldown" in r.safety_flags
        is_not_escalation = r.orch_action != "send_admin_alert"
        assert has_cooldown_flag or is_not_escalation

    def test_gate_no_user_dm_high_risk(self):
        r = run_scenario(
            "narxi qancha",
            build_memory(followup_count=5, temp="warm"),
        )
        if r.policy_risk == "high":
            assert r.orch_action != "send_user_reply"

    def test_gate_no_fake_discount(self):
        for text in ("qimmat", "arzonroq bormi", "дорого"):
            r = run_scenario(text, build_memory(temp="warm"))
            if r.orch_user_text:
                assert "eng arzon" not in r.orch_user_text.lower()
                assert "10%" not in r.orch_user_text
                assert "50%" not in r.orch_user_text

    def test_gate_no_same_day_promise(self):
        for text in ("bugun kerak", "ertaga kerak", "shoshilinch"):
            r = run_scenario(text, build_memory(temp="warm"))
            if r.orch_user_text:
                assert "bugun qilamiz" not in r.orch_user_text.lower()

    def test_gate_no_phone_in_trace(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        trace = AgentResponseOrchestrator.build_trace(
            signal={"phone": "+998901111111"},
            decision={},
            offer={},
            policy={},
            action="test",
            source="test",
        )
        assert "+998" not in str(trace)

    def test_gate_followup_cap_prevents_spam(self):
        r = run_scenario(
            "katalog bormi",
            build_memory(followup_count=5, temp="warm"),
        )
        assert r.orch_allowed is False

    def test_gate_hot_lead_not_ignored(self):
        r = run_scenario(
            memory=build_memory(lead_score=80, temp="hot"),
        )
        assert r.policy_action in ("escalate_admin", "handoff_operator", "reply_now")

    def test_gate_discount_says_operator(self):
        r = run_scenario("chegirma bormi", build_memory(temp="warm"))
        if r.orch_user_text:
            assert "operator" in r.orch_user_text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# R) Extra scenarios to reach 80+
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtraScenarios:
    def test_r70_measurement_warm(self):
        r = run_scenario("o'lchov kerak", build_memory(temp="warm"))
        assert r.signal_intent == "wants_measurement"

    def test_r71_zamer_ru(self):
        r = run_scenario("замер нужен", build_memory(temp="warm"))
        assert r.signal_intent == "wants_measurement"

    def test_r72_skidka_ru(self):
        r = run_scenario("скидка", build_memory(temp="warm"))
        assert r.signal_intent == "wants_discount"

    def test_r73_kerakmas_single_word(self):
        r = run_scenario("kerakmas", build_memory(temp="hot"))
        assert r.signal_intent == "stop_request"
        assert r.orch_action == "disable_agent"

    def test_r74_bekor_stop(self):
        r = run_scenario("bekor", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"

    def test_r75_warm_area_price_calc(self):
        r = run_scenario(
            memory=build_memory(temp="warm", area=25.0),
        )
        assert r.offer_type in ("price_calculation", "design_help")

    def test_r76_comparing_objection(self):
        r = run_scenario(
            "boshqa firma bilan taqqoslayapman",
            build_memory(temp="warm"),
        )
        assert r.signal_objection == "comparing"
        assert r.offer_type == "portfolio_social_proof"

    def test_r77_family_objection(self):
        r = run_scenario(
            "erim bilan maslahat qilaman",
            build_memory(temp="warm"),
        )
        assert r.signal_objection == "spouse_family_decision"

    def test_r78_budget_mention(self):
        from core.services.lead_signal_service import LeadSignalService

        sig = LeadSignalService.extract_signals("budjetim 10 mln")
        assert sig.budget_amount == 10_000_000

    def test_r79_stoimost_ru(self):
        r = run_scenario("стоимость потолка", build_memory(temp="warm"))
        assert r.signal_intent == "wants_price"

    def test_r80_otmena_ru(self):
        r = run_scenario("отмена", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"

    def test_r81_qiziqmayman(self):
        r = run_scenario("qiziqmayman", build_memory(temp="warm"))
        assert r.signal_intent == "stop_request"

    def test_r82_boshlaymiz_order(self):
        r = run_scenario("boshlaymiz", build_memory(temp="warm"))
        assert r.signal_intent == "wants_order"

    def test_r83_pending_blocks_schedule(self):
        r = run_scenario(
            memory=build_memory(
                state="browsing_catalog",
                temp="warm",
                has_pending=True,
            ),
        )
        assert "pending_followup_exists" in r.safety_flags or r.policy_action != "schedule_followup"
