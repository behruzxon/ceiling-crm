"""Integration tests for price estimate history flow — Step 7."""

from __future__ import annotations

from core.services.crm_price_estimate_history_service import (
    build_history,
    sanitize_metadata,
    sanitize_preview,
)


class TestGulliEstimate:
    def test_20kv_gulli_estimate_shown(self) -> None:
        traces = [
            {
                "price_estimate": 2600000,
                "area_m2": 20,
                "design_type": "gulli",
                "timestamp": "2025-01-15T10:30",
            }
        ]
        result = build_history(contact={"id": 10}, traces=traces)
        assert result.summary.total_estimates == 1
        item = result.items[0]
        assert item.total_uzs == 2600000
        assert item.area_m2 == 20.0
        assert item.design_key == "gulli"
        assert item.design_title == "Gulli"

    def test_gulli_rate_calculated(self) -> None:
        traces = [
            {
                "price_estimate": 2600000,
                "area_m2": 20,
                "design_type": "gulli",
                "timestamp": "2025-01-15",
            }
        ]
        result = build_history(contact={"id": 11}, traces=traces)
        assert result.items[0].rate_uzs_per_m2 == 130000


class TestHiTechEstimate:
    def test_5x4_led_estimate_shown(self) -> None:
        traces = [
            {
                "price_estimate": 2400000,
                "area_m2": 20,
                "design_type": "hi-tech",
                "timestamp": "2025-01-15T11:00",
            }
        ]
        result = build_history(contact={"id": 20}, traces=traces)
        assert result.summary.total_estimates == 1
        item = result.items[0]
        assert item.total_uzs == 2400000
        assert item.design_title == "Hi-tech"


class TestHandoffAfterEstimate:
    def test_handoff_marked(self) -> None:
        traces = [{"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-15T10:00"}]
        msgs = [
            {"text": "Operatorga ulang", "direction": "inbound"},
            {"text": "Ok", "direction": "outbound", "sender_type": "operator"},
        ]
        result = build_history(contact={"id": 30}, traces=traces, messages=msgs)
        assert result.items[0].handoff_after_estimate is True
        assert result.summary.handoff_after_estimate_count == 1

    def test_no_handoff_when_no_operator(self) -> None:
        traces = [{"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-15T10:00"}]
        msgs = [{"text": "Rahmat", "direction": "inbound"}]
        result = build_history(contact={"id": 31}, traces=traces, messages=msgs)
        assert result.items[0].handoff_after_estimate is False


class TestEmptyContact:
    def test_empty_safe(self) -> None:
        result = build_history(contact={"id": 40})
        assert result.items == []
        assert result.summary.total_estimates == 0

    def test_no_metadata_safe(self) -> None:
        result = build_history(contact={"id": 41, "metadata": {}})
        assert result.items == []


class TestNoExternalCalls:
    def test_no_telegram_send(self) -> None:
        import core.services.crm_price_estimate_history_service as svc

        source = open(svc.__file__, encoding="utf-8").read()
        assert "send_message" not in source
        assert "Bot(" not in source

    def test_no_openai_call(self) -> None:
        import core.services.crm_price_estimate_history_service as svc

        source = open(svc.__file__, encoding="utf-8").read()
        assert "import openai" not in source
        assert "ChatCompletion" not in source

    def test_no_token_in_service(self) -> None:
        import core.services.crm_price_estimate_history_service as svc

        source = open(svc.__file__, encoding="utf-8").read()
        assert "BOT_TOKEN" not in source
        assert "get_secret_value" not in source


class TestPrivacy:
    def test_preview_redacts_secrets(self) -> None:
        result = sanitize_preview("key sk-abc123def456ghij here")
        assert "sk-abc123def456ghij" not in (result or "")

    def test_metadata_strips_unsafe(self) -> None:
        result = sanitize_metadata({"area_m2": 20, "password": "secret"})
        assert "secret" not in (result or "")
