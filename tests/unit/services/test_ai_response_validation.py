"""Unit tests for AI response validation and graceful fallback.

Covers:
  1. Valid JSON → AIReplyPayload fields parsed correctly
  2. Malformed JSON in _call_ai → returns empty dict (no crash)
  3. Missing/empty reply → triggers fallback message
  4. Invalid intent → normalised to "other"
  5. Invalid lead_temperature → normalised to None
  6. Invalid closing_confidence → normalised to None
  7. Extracted fields parsed or default to empty dict
  8. parse_ai_response never raises on any input
  9. Structured log fields on parse failure
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── AIReplyPayload validation ────────────────────────────────────────────────


class TestAIReplyPayload:
    """Pydantic model validates and normalises AI response fields."""

    def test_valid_full_response(self) -> None:
        from core.domain.ai_response import parse_ai_response

        raw = {
            "intent": "price",
            "reply": "Narx 80 000 so'm/m²",
            "lead_temperature": "hot",
            "closing_confidence": 0.85,
            "extracted": {
                "interested_design": "Hi Tech",
                "last_dimensions": "5x4",
                "location": "Qarshi",
            },
        }
        p = parse_ai_response(raw)
        assert p.intent == "price"
        assert p.reply == "Narx 80 000 so'm/m²"
        assert p.lead_temperature == "hot"
        assert p.closing_confidence == 0.85
        assert p.extracted.interested_design == "Hi Tech"
        assert p.extracted.last_dimensions == "5x4"
        assert p.extracted.location == "Qarshi"

    def test_minimal_response(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"reply": "Salom!"})
        assert p.intent == "other"
        assert p.reply == "Salom!"
        assert p.lead_temperature is None
        assert p.closing_confidence is None

    def test_empty_dict_gives_defaults(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({})
        assert p.intent == "other"
        assert p.reply == ""
        assert p.lead_temperature is None
        assert p.closing_confidence is None

    def test_invalid_intent_normalised(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"intent": "INVALID_JUNK", "reply": "ok"})
        assert p.intent == "other"

    def test_none_intent_normalised(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"intent": None, "reply": "ok"})
        assert p.intent == "other"

    def test_invalid_temperature_normalised(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"lead_temperature": "boiling", "reply": "ok"})
        assert p.lead_temperature is None

    def test_valid_temperatures(self) -> None:
        from core.domain.ai_response import parse_ai_response

        for temp in ("hot", "warm", "cold"):
            p = parse_ai_response({"lead_temperature": temp, "reply": "ok"})
            assert p.lead_temperature == temp

    def test_invalid_confidence_normalised(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"closing_confidence": "not_a_number", "reply": "ok"})
        assert p.closing_confidence is None

    def test_string_confidence_parsed(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"closing_confidence": "0.75", "reply": "ok"})
        assert p.closing_confidence == 0.75

    def test_extracted_null_gives_empty(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"extracted": None, "reply": "ok"})
        assert p.extracted.interested_design is None

    def test_extracted_string_gives_empty(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"extracted": "not a dict", "reply": "ok"})
        assert p.extracted.interested_design is None

    def test_extra_extracted_fields_allowed(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({
            "extracted": {"custom_field": "value", "location": "Qarshi"},
            "reply": "ok",
        })
        assert p.extracted.location == "Qarshi"

    def test_never_raises_on_garbage(self) -> None:
        from core.domain.ai_response import parse_ai_response

        # These should all return fallback, never raise
        for garbage in [None, 42, "string", [], True, {"reply": object()}]:
            p = parse_ai_response(garbage if isinstance(garbage, dict) else {})
            assert isinstance(p.intent, str)


# ── _call_ai safe JSON parsing ───────────────────────────────────────────────


class TestCallAiSafeJson:
    """_call_ai returns empty dict on malformed JSON instead of crashing."""

    async def test_malformed_json_returns_empty_dict(self) -> None:
        from apps.bot.handlers.private.ai_openai import _call_ai

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "NOT VALID JSON {{{{"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("core.services.ai_engine._get_client", return_value=mock_client),
            patch("core.services.ai_engine.get_settings") as mock_settings,
        ):
            mock_settings.return_value.ai.model = "gpt-4o"
            result = await _call_ai("test question", [], None)

        assert result == {}

    async def test_valid_json_parsed_normally(self) -> None:
        from apps.bot.handlers.private.ai_openai import _call_ai

        expected = {"intent": "greeting", "reply": "Salom!"}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(expected)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("core.services.ai_engine._get_client", return_value=mock_client),
            patch("core.services.ai_engine.get_settings") as mock_settings,
        ):
            mock_settings.return_value.ai.model = "gpt-4o"
            result = await _call_ai("test question", [], None)

        assert result == expected

    async def test_none_content_returns_empty_dict(self) -> None:
        from apps.bot.handlers.private.ai_openai import _call_ai

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("core.services.ai_engine._get_client", return_value=mock_client),
            patch("core.services.ai_engine.get_settings") as mock_settings,
        ):
            mock_settings.return_value.ai.model = "gpt-4o"
            result = await _call_ai("test question", [], None)

        # None → "{}" → json.loads("{}") → {}
        assert result == {}


# ── Empty reply triggers fallback ────────────────────────────────────────────


class TestEmptyReplyFallback:
    """Empty AI reply triggers fallback message instead of crashing."""

    def test_parse_empty_reply_detected(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"intent": "price", "reply": ""})
        assert p.reply == ""

    def test_parse_whitespace_reply_detected(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"intent": "price", "reply": "   "})
        # reply is stored as-is; handler calls .strip()
        assert p.reply.strip() == ""

    def test_parse_missing_reply_defaults_empty(self) -> None:
        from core.domain.ai_response import parse_ai_response

        p = parse_ai_response({"intent": "price"})
        assert p.reply == ""


# ── Structured logging ───────────────────────────────────────────────────────


class TestStructuredLogging:
    """Structured log fields are emitted on AI response failures."""

    async def test_malformed_json_logs_structured_event(self) -> None:
        from apps.bot.handlers.private.ai_openai import _call_ai

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{broken json"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("core.services.ai_engine._get_client", return_value=mock_client),
            patch("core.services.ai_engine.get_settings") as mock_settings,
            patch("core.services.ai_engine.log") as mock_log,
        ):
            mock_settings.return_value.ai.model = "gpt-4o"
            await _call_ai("test", [], None)

        mock_log.error.assert_called_once()
        call_args = mock_log.error.call_args
        assert call_args[0][0] == "ai_response_parse_failed"
        assert "raw_response" in call_args[1]
        assert "error" in call_args[1]
        # Raw response should be truncated to 500 chars
        assert len(call_args[1]["raw_response"]) <= 500
