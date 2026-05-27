"""Step I tests: AI message composer, validation, fallback, prompts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.ai_message_composer_service import (
    _build_user_prompt,
    compose_followup,
    validate_ai_output,
)
from core.services.followup_scheduler_service import FollowupSchedulerService

# ── Feature flags ──────────────────────────────────────────────────────────


class TestComposerFlags:
    def test_flag_default_false(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_ai_composer_enabled is False

    def test_model_default(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_ai_composer_model == "gpt-4o-mini"

    def test_timeout_default(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_ai_composer_timeout_seconds == 8

    def test_max_tokens_default(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_ai_composer_max_tokens == 180


# ── compose_followup fallback ──────────────────────────────────────────────


class TestComposeFallback:
    @pytest.mark.asyncio
    async def test_disabled_returns_fallback(self) -> None:
        result = await compose_followup("catalog", {}, "FALLBACK")
        assert result == "FALLBACK"

    @pytest.mark.asyncio
    async def test_openai_error_returns_fallback(self) -> None:
        with patch(
            "shared.config.get_settings",
        ) as mock_settings:
            biz = MagicMock()
            biz.agent_ai_composer_enabled = True
            biz.agent_ai_composer_model = "gpt-4o-mini"
            biz.agent_ai_composer_timeout_seconds = 3
            biz.agent_ai_composer_max_tokens = 100
            mock_settings.return_value.business = biz

            with patch(
                "infrastructure.ai.openai_client.get_openai_client",
                side_effect=RuntimeError("API down"),
            ):
                result = await compose_followup("catalog", {}, "FALLBACK")
        assert result == "FALLBACK"

    @pytest.mark.asyncio
    async def test_ai_success_returns_ai_text(self) -> None:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Salom! Dizayn yoqdimi?"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch(
            "shared.config.get_settings",
        ) as mock_settings:
            biz = MagicMock()
            biz.agent_ai_composer_enabled = True
            biz.agent_ai_composer_model = "gpt-4o-mini"
            biz.agent_ai_composer_timeout_seconds = 8
            biz.agent_ai_composer_max_tokens = 180
            mock_settings.return_value.business = biz

            with patch(
                "infrastructure.ai.openai_client.get_openai_client",
                return_value=mock_client,
            ):
                result = await compose_followup("catalog", {"full_name": "Ali"}, "FALLBACK")
        assert result == "Salom! Dizayn yoqdimi?"

    @pytest.mark.asyncio
    async def test_invalid_ai_output_returns_fallback(self) -> None:
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Eng arzon narx bizda!" * 20

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch(
            "shared.config.get_settings",
        ) as mock_settings:
            biz = MagicMock()
            biz.agent_ai_composer_enabled = True
            biz.agent_ai_composer_model = "gpt-4o-mini"
            biz.agent_ai_composer_timeout_seconds = 8
            biz.agent_ai_composer_max_tokens = 180
            mock_settings.return_value.business = biz

            with patch(
                "infrastructure.ai.openai_client.get_openai_client",
                return_value=mock_client,
            ):
                result = await compose_followup("catalog", {}, "FALLBACK")
        assert result == "FALLBACK"


# ── validate_ai_output ─────────────────────────────────────────────────────


class TestValidation:
    def test_valid_text(self) -> None:
        ok, r = validate_ai_output("Salom! Narx kerakmi?", "catalog", {})
        assert ok is True

    def test_empty_text(self) -> None:
        ok, r = validate_ai_output("", "catalog", {})
        assert ok is False
        assert r == "empty"

    def test_too_long(self) -> None:
        ok, r = validate_ai_output("x" * 501, "catalog", {})
        assert ok is False
        assert r == "too_long"

    def test_unsafe_100_percent(self) -> None:
        ok, r = validate_ai_output("100% kafolat beramiz!", "catalog", {})
        assert ok is False
        assert r == "unsafe_pattern"

    def test_unsafe_eng_arzon(self) -> None:
        ok, r = validate_ai_output("Eng arzon narx bizda", "price", {})
        assert ok is False
        assert r == "unsafe_pattern"

    def test_unsafe_aniq_narx(self) -> None:
        ok, r = validate_ai_output("Aniq narx aytaman", "price", {})
        assert ok is False
        assert r == "unsafe_pattern"

    def test_unsafe_phone_leak(self) -> None:
        ok, r = validate_ai_output("Qo'ng'iroq qiling +998901234567", "price", {})
        assert ok is False
        assert r == "unsafe_pattern"

    def test_unsafe_token_leak(self) -> None:
        ok, r = validate_ai_output("token=abc123", "catalog", {})
        assert ok is False
        assert r == "unsafe_pattern"

    def test_invented_price_no_memory(self) -> None:
        ok, r = validate_ai_output("Narxi 5000000 so'm", "price", {})
        assert ok is False
        assert r == "invented_price"

    def test_price_ok_with_memory(self) -> None:
        ok, r = validate_ai_output(
            "Narxi 5000000 so'm",
            "price",
            {"estimated_price": 5_000_000},
        )
        assert ok is True


# ── Prompt building ────────────────────────────────────────────────────────


class TestPromptBuilding:
    def test_catalog_prompt_includes_designs(self) -> None:
        prompt = _build_user_prompt(
            "catalog",
            {
                "full_name": "Bobur",
                "interested_designs": ["gulli", "mramor"],
            },
        )
        assert "gulli" in prompt
        assert "mramor" in prompt
        assert "Bobur" in prompt

    def test_catalog_prompt_no_designs(self) -> None:
        prompt = _build_user_prompt("catalog", {})
        assert "kvadrat" in prompt.lower() or "narx" in prompt.lower()

    def test_price_prompt_includes_area(self) -> None:
        prompt = _build_user_prompt(
            "price",
            {
                "area_m2": 25.0,
                "estimated_price": 5_000_000,
                "ceiling_type": "gulli",
            },
        )
        assert "25" in prompt
        assert "5,000,000" in prompt
        assert "gulli" in prompt

    def test_abandoned_prompt_no_phone(self) -> None:
        prompt = _build_user_prompt(
            "abandoned_order",
            {
                "full_name": "Ali",
            },
        )
        assert "Ali" in prompt
        assert "yo'q" in prompt.lower()

    def test_abandoned_prompt_with_phone(self) -> None:
        prompt = _build_user_prompt(
            "abandoned_order",
            {
                "full_name": "Ali",
                "phone_masked": "+998**…**67",
            },
        )
        assert "bor" in prompt.lower()


# ── build_message_ai ───────────────────────────────────────────────────────


class TestBuildMessageAI:
    @pytest.mark.asyncio
    async def test_no_memory_returns_fallback(self) -> None:
        text, buttons = await FollowupSchedulerService.build_message_ai("catalog")
        assert "Katalog" in text
        assert len(buttons) == 3

    @pytest.mark.asyncio
    async def test_buttons_unchanged_with_ai(self) -> None:
        with patch(
            "core.services.ai_message_composer_service.compose_followup",
            return_value="AI text",
        ):
            text, buttons = await FollowupSchedulerService.build_message_ai(
                "price",
                memory_data={"full_name": "Test"},
            )
        assert len(buttons) == 3

    @pytest.mark.asyncio
    async def test_ai_error_returns_fallback_buttons(self) -> None:
        with patch(
            "core.services.ai_message_composer_service.compose_followup",
            side_effect=RuntimeError("fail"),
        ):
            text, buttons = await FollowupSchedulerService.build_message_ai(
                "abandoned_order",
                memory_data={"full_name": "X"},
            )
        assert "Buyurtma" in text or "davom" in text
        assert len(buttons) == 3


# ── No regression ─────────────────────────────────────────────────────────


class TestNoRegression:
    def test_sync_build_message_still_works(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("catalog")
        assert "Katalog" in text
        assert len(buttons) == 3

    def test_price_sync_unchanged(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("price")
        assert "Hisob" in text
        assert len(buttons) == 3

    def test_order_sync_unchanged(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("abandoned_order")
        assert "Buyurtma" in text or "davom" in text
        assert len(buttons) == 3
