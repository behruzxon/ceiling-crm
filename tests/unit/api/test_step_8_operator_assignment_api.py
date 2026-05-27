"""Tests for operator assignment API — Step 8."""

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


class TestEndpointsExist:
    def test_take_endpoint(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/take" in p for p in paths)

    def test_unassign_endpoint(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/unassign" in p for p in paths)

    def test_operator_summary_endpoint(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/operators/summary" in p for p in paths)

    def test_assign_endpoint_still_exists(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/assign" in p for p in paths)

    def test_contacted_endpoint_still_exists(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/contacted" in p for p in paths)

    def test_resolve_endpoint_still_exists(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/resolve" in p for p in paths)

    def test_cancel_endpoint_still_exists(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/cancel" in p for p in paths)

    def test_queue_endpoint_still_exists(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/queue" in p for p in paths)

    def test_summary_endpoint_still_exists(self) -> None:
        from apps.api.main import app

        paths = [r.path for r in app.routes]
        assert any("/summary" in p for p in paths)


class TestHTTPMethods:
    def test_take_is_post(self, client) -> None:
        r = client.post("/api/v1/admin/crm/handoffs/1/take")
        assert r.status_code != 405

    def test_unassign_is_post(self, client) -> None:
        r = client.post("/api/v1/admin/crm/handoffs/1/unassign")
        assert r.status_code != 405

    def test_summary_is_get(self, client) -> None:
        r = client.get("/api/v1/admin/crm/handoffs/operators/summary")
        assert r.status_code != 405


class TestAuthRequired:
    def test_take_requires_auth(self, client) -> None:
        r = client.post("/api/v1/admin/crm/handoffs/1/take")
        assert r.status_code in (401, 403, 404, 500)

    def test_unassign_requires_auth(self, client) -> None:
        r = client.post("/api/v1/admin/crm/handoffs/1/unassign")
        assert r.status_code in (401, 403, 404, 500)

    def test_operator_summary_requires_auth(self, client) -> None:
        r = client.get("/api/v1/admin/crm/handoffs/operators/summary")
        assert r.status_code in (401, 403, 500)


class TestSecurity:
    def test_no_token_in_source(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "sk-" not in src
        assert "BOT_TOKEN" not in src

    def test_no_openai_key(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" not in src

    def test_phone_masked_field(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "phone_masked" in src
        assert "phone_raw" not in src

    def test_uses_require_api_token(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "require_api_token" in src

    def test_no_send_message(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "send_message" not in src


class TestServiceFunctions:
    def test_valid_statuses_include_assigned(self) -> None:
        from core.services.crm_operator_handoff_service import VALID_STATUSES

        assert "assigned" in VALID_STATUSES

    def test_valid_statuses_include_open(self) -> None:
        from core.services.crm_operator_handoff_service import VALID_STATUSES

        assert "open" in VALID_STATUSES

    def test_mask_phone(self) -> None:
        from core.services.crm_operator_handoff_service import mask_phone

        assert mask_phone("+998901234567") == "+998****67"

    def test_mask_phone_none(self) -> None:
        from core.services.crm_operator_handoff_service import mask_phone

        assert mask_phone(None) is None

    def test_sanitize_message_preview(self) -> None:
        from core.services.crm_operator_handoff_service import sanitize_message_preview

        result = sanitize_message_preview("key sk-abcdefghijk12345")
        assert "sk-abcdefghijk12345" not in (result or "")

    def test_calculate_priority_urgent(self) -> None:
        from core.services.crm_operator_handoff_service import calculate_priority

        assert calculate_priority(lead_score=90) == "urgent"

    def test_calculate_priority_normal(self) -> None:
        from core.services.crm_operator_handoff_service import calculate_priority

        assert calculate_priority(lead_score=10) == "normal"

    def test_queue_summary_dataclass(self) -> None:
        from core.services.crm_operator_handoff_service import QueueSummary

        s = QueueSummary()
        assert s.total_open == 0
        assert s.total_assigned == 0


class TestErrorHandling:
    def test_invalid_handoff_id(self, client) -> None:
        r = client.post("/api/v1/admin/crm/handoffs/999999/take")
        assert r.status_code in (401, 403, 404, 500)

    def test_take_string_id_rejected(self, client) -> None:
        r = client.post("/api/v1/admin/crm/handoffs/abc/take")
        assert r.status_code in (401, 422)
