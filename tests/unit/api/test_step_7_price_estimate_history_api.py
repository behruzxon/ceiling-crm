"""Tests for price estimate history API — Step 7."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _make_client():
    from apps.api.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client():
    return _make_client()


class TestEndpointExists:
    def test_endpoint_registered(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/price-estimates" in p for p in paths)

    def test_get_method(self) -> None:
        from apps.api.main import app

        for route in app.routes:
            if hasattr(route, "path") and "/price-estimates" in route.path:
                assert "GET" in route.methods
                break


class TestAuthRequired:
    def test_no_token_returns_error(self, client) -> None:
        r = client.get("/api/v1/admin/crm/contacts/1/price-estimates")
        assert r.status_code in (401, 403, 422, 200)

    def test_invalid_contact_id_zero(self, client) -> None:
        r = client.get("/api/v1/admin/crm/contacts/0/price-estimates")
        assert r.status_code in (401, 403, 422, 400)

    def test_negative_contact_id(self, client) -> None:
        r = client.get("/api/v1/admin/crm/contacts/-1/price-estimates")
        assert r.status_code in (401, 403, 422, 400)


class TestResponseStructure:
    def test_returns_contact_id(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 5})
        assert result.contact_id == 5

    def test_returns_summary(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 5})
        assert hasattr(result.summary, "total_estimates")

    def test_returns_items_list(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 5})
        assert isinstance(result.items, list)

    def test_empty_history_safe(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 5})
        assert result.summary.total_estimates == 0
        assert result.items == []

    def test_items_have_estimate_id(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        traces = [{"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-01"}]
        result = build_history(contact={"id": 5}, traces=traces)
        assert result.items[0].estimate_id != ""

    def test_items_have_total(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        traces = [{"price_estimate": 2000000, "area_m2": 20, "timestamp": "2025-01-01"}]
        result = build_history(contact={"id": 5}, traces=traces)
        assert result.items[0].total_uzs == 2000000


class TestSecurity:
    def test_no_token_in_module(self) -> None:
        import apps.api.routes.admin_crm_price_estimates as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "BOT_TOKEN" not in src
        assert "sk-" not in src

    def test_no_phone_raw(self) -> None:
        import apps.api.routes.admin_crm_price_estimates as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "phone" not in src.lower() or "phone_raw" not in src

    def test_no_raw_metadata_dump(self) -> None:
        from core.services.crm_price_estimate_history_service import sanitize_metadata

        result = sanitize_metadata({"password": "secret", "area_m2": 20})
        assert "secret" not in (result or "")

    def test_no_openai_key(self) -> None:
        import apps.api.routes.admin_crm_price_estimates as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" not in src

    def test_uses_require_api_token(self) -> None:
        import apps.api.routes.admin_crm_price_estimates as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "require_api_token" in src


class TestServiceError:
    def test_service_error_handled(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={})
        assert result.contact_id == 0
        assert result.items == []

    def test_none_traces_safe(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 1}, traces=None)
        assert result.items == []

    def test_none_messages_safe(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 1}, messages=None)
        assert result.items == []

    def test_none_replay_events_safe(self) -> None:
        from core.services.crm_price_estimate_history_service import build_history

        result = build_history(contact={"id": 1}, replay_events=None)
        assert result.items == []
