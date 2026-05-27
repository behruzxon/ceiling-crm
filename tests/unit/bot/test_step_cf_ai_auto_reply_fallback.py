"""Tests for Step CF — AI Auto-Reply & Fallback."""

from __future__ import annotations

from apps.bot.handlers.private.ai_support_auto_reply import (
    _AI_DAILY_LIMIT,
    _check_ai_rate_limit,
    _detect_simple_intent,
    _reset_auto_reply_counter,
    _try_auto_reply,
)


class TestSimpleIntentDetection:
    def test_price_narx(self):
        assert _detect_simple_intent("narx qancha") == "price"

    def test_price_qancha(self):
        assert _detect_simple_intent("qancha turadi") == "price"

    def test_price_baho(self):
        assert _detect_simple_intent("baho qanday") == "price"

    def test_material_rang(self):
        assert _detect_simple_intent("rang bormi") == "material"

    def test_material_dizayn(self):
        assert _detect_simple_intent("dizayn ko'rsat") == "material"

    def test_material_tekstura(self):
        assert _detect_simple_intent("tekstura qanday") == "material"

    def test_package_paket(self):
        assert _detect_simple_intent("paket bor") == "package"

    def test_package_premium(self):
        assert _detect_simple_intent("premium paket") == "package"

    def test_package_standart(self):
        assert _detect_simple_intent("standart nima") == "package"

    def test_none_for_greeting(self):
        assert _detect_simple_intent("salom") is None

    def test_none_for_generic(self):
        assert _detect_simple_intent("yaxshi") is None

    def test_none_for_empty(self):
        assert _detect_simple_intent("") is None


class TestRateLimitConfig:
    def test_daily_limit_value(self):
        assert _AI_DAILY_LIMIT == 100

    def test_rate_limit_importable(self):
        assert callable(_check_ai_rate_limit)


class TestAutoReplyImports:
    def test_try_auto_reply_importable(self):
        assert callable(_try_auto_reply)

    def test_reset_counter_importable(self):
        assert callable(_reset_auto_reply_counter)


class TestAutoSalesService:
    def test_should_escalate_importable(self):
        from core.services.auto_sales_service import should_escalate

        assert callable(should_escalate)

    def test_decide_auto_reply_importable(self):
        from core.services.auto_sales_service import decide_auto_reply

        assert callable(decide_auto_reply)

    def test_generate_auto_reply_importable(self):
        from core.services.auto_sales_service import generate_auto_reply

        assert callable(generate_auto_reply)

    def test_build_escalation_alert_importable(self):
        from core.services.auto_sales_service import build_escalation_alert

        assert callable(build_escalation_alert)


class TestOpenAIFallback:
    def test_call_ai_importable(self):
        from apps.bot.handlers.private.ai_openai import _call_ai

        assert callable(_call_ai)

    def test_context_block_builder(self):
        from apps.bot.handlers.private.ai_openai import _build_context_block

        result = _build_context_block({}, None)
        assert result is None or isinstance(result, str)

    def test_context_block_with_profile(self):
        from apps.bot.handlers.private.ai_openai import _build_context_block

        profile = {
            "interested_design": "Gulli",
            "last_dimensions": "20 m2",
        }
        result = _build_context_block(profile, None)
        assert result is not None
        assert "Gulli" in result

    def test_context_block_with_summary(self):
        from apps.bot.handlers.private.ai_openai import _build_context_block

        result = _build_context_block({}, "User asked about pricing")
        assert result is not None
        assert "pricing" in result.lower()

    def test_max_tokens_constant(self):
        from apps.bot.handlers.private.ai_openai import _MAX_REQUEST_TOKENS

        assert _MAX_REQUEST_TOKENS == 8000

    def test_max_messages_constant(self):
        from apps.bot.handlers.private.ai_openai import _MAX_MESSAGES

        assert _MAX_MESSAGES == 12

    def test_history_to_send_constant(self):
        from apps.bot.handlers.private.ai_openai import _HISTORY_TO_SEND

        assert _HISTORY_TO_SEND == 8
