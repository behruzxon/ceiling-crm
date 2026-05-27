"""Tests for Step X — Agent execution approve/reject API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.agent_execution_queue_service import AgentExecutionQueueService
from infrastructure.database.models.agent_execution_record import (
    AgentExecutionRecordModel,
)


def _rec(
    *,
    execution_id: str = "test-001",
    status: str = "proposed",
    action: str = "send_user_reply",
    user_id: int = 12345,
    risk: str = "low",
    channel: str = "user_dm",
    payload: dict | None = None,
    expires_minutes: int = 30,
) -> AgentExecutionRecordModel:
    now = datetime.now(UTC)
    r = MagicMock(spec=AgentExecutionRecordModel)
    r.execution_id = execution_id
    r.telegram_user_id = user_id
    r.action = action
    r.mode = "approval_required"
    r.status = status
    r.risk_level = risk
    r.channel = channel
    r.payload_json = payload or {"message_text": "Salom"}
    r.result_json = None
    r.message_text_hash = "abc"
    r.approved_by = None
    r.approved_at = None
    r.rejected_by = None
    r.rejected_at = None
    r.rejection_reason = None
    r.blocked_reason = None
    r.created_at = now
    r.expires_at = now + timedelta(minutes=expires_minutes)
    r.executed_at = None
    r.failed_at = None
    r.last_error = None
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# 1. API route availability
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteAvailability:
    def test_detail_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("{execution_id}" in p and "executions" in p for p in paths)

    def test_approve_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("approve" in p for p in paths)

    def test_reject_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("reject" in p for p in paths)

    def test_expire_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("expire" in p for p in paths)

    def test_router_has_auth_dependency(self):
        from apps.api.routes.admin_agent_metrics import router

        assert len(router.dependencies) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Sanitize record for API
# ═══════════════════════════════════════════════════════════════════════════════


class TestSanitizeForAPI:
    def test_basic_sanitize(self):
        record = _rec()
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        assert d["execution_id"] == "test-001"
        assert d["status"] == "proposed"

    def test_phone_redacted(self):
        record = _rec(payload={"message_text": "Call +998901234567"})
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        assert "+998901234567" not in str(d)

    def test_token_redacted(self):
        record = _rec(payload={"message_text": "sk-secret123abc"})
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        assert "sk-secret" not in str(d)

    def test_long_message_truncated(self):
        long_msg = "a" * 200
        record = _rec(payload={"message_text": long_msg})
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        preview = d["payload_preview"]["message_text"]
        assert len(preview) <= 104  # 100 + "..."

    def test_safe_message_preserved(self):
        record = _rec(payload={"message_text": "Salom!"})
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        assert d["payload_preview"]["message_text"] == "Salom!"

    def test_includes_dates(self):
        record = _rec()
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        assert "created_at" in d
        assert "expires_at" in d

    def test_includes_approval_info(self):
        record = _rec()
        d = AgentExecutionQueueService.sanitize_record_for_api(record)
        assert "approved_by" in d
        assert "rejected_by" in d


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Expire method
# ═══════════════════════════════════════════════════════════════════════════════


class TestExpireMethod:
    async def test_expire_proposed(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.expire("test-001")
        assert ok is True
        assert record.status == "expired"

    async def test_expire_not_found(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.expire("missing")
        assert ok is False
        assert reason == "not_found"

    async def test_expire_final_rejected(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="executed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.expire("test-001")
        assert ok is False
        assert "already_executed" in reason


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Approve lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestApproveLifecycle:
    async def test_approve_proposed_ok(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, _ = await svc.approve("test-001", admin_id=999)
        assert ok is True
        assert record.status == "approved"

    async def test_approve_expired_fails(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="proposed", expires_minutes=-10)
        record.expires_at = datetime.now(UTC) - timedelta(minutes=10)
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test-001", admin_id=999)
        assert ok is False
        assert reason == "expired"

    async def test_approve_executed_fails(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="executed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, reason = await svc.approve("test-001", admin_id=999)
        assert ok is False

    async def test_approve_rejected_fails(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="rejected")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, _ = await svc.approve("test-001", admin_id=999)
        assert ok is False


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Reject lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestRejectLifecycle:
    async def test_reject_proposed_ok(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, _ = await svc.reject("test-001", admin_id=999, reason="not safe")
        assert ok is True
        assert record.rejection_reason == "not safe"

    async def test_reject_executed_fails(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="executed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        ok, _ = await svc.reject("test-001", admin_id=999)
        assert ok is False

    async def test_reject_reason_truncated(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        record = _rec(status="proposed")
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=record)),
        )
        svc = AgentExecutionQueueService(session)
        long_reason = "x" * 500
        ok, _ = await svc.reject("test-001", admin_id=999, reason=long_reason)
        assert ok is True
        assert len(record.rejection_reason) <= 255


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettings:
    def test_api_approval_default_false(self):
        from shared.config.settings import BusinessSettings

        assert (
            BusinessSettings.model_fields["agent_execution_api_approval_enabled"].default is False
        )

    def test_check_approval_raises_when_disabled(self):
        from unittest.mock import patch

        from fastapi import HTTPException

        from apps.api.routes.admin_agent_metrics import _check_approval_enabled

        with patch("shared.config.get_settings") as mock:
            mock.return_value.business.agent_execution_api_approval_enabled = False
            with pytest.raises(HTTPException) as exc_info:
                _check_approval_enabled()
            assert exc_info.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Frontend template
# ═══════════════════════════════════════════════════════════════════════════════


class TestFrontend:
    def test_template_has_approve_button(self):
        from pathlib import Path

        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "approveExec" in html

    def test_template_has_reject_button(self):
        from pathlib import Path

        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "rejectExec" in html

    def test_template_has_confirm_dialog(self):
        from pathlib import Path

        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "confirm" in html

    def test_template_has_reason_prompt(self):
        from pathlib import Path

        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "prompt" in html

    def test_template_no_raw_payload(self):
        from pathlib import Path

        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "payload_json" not in html


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Non-regression
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonRegression:
    def test_pending_endpoint_still_works(self):
        from apps.api.routes.admin_agent_metrics import router

        route_paths = [r.path for r in router.routes]
        assert any("pending" in p for p in route_paths)

    def test_overview_endpoint_still_works(self):
        from apps.api.routes.admin_agent_metrics import router

        route_paths = [r.path for r in router.routes]
        assert any("overview" in p for p in route_paths)

    def test_health_endpoint_still_works(self):
        from apps.api.routes.admin_agent_metrics import router

        route_paths = [r.path for r in router.routes]
        assert any("health" in p for p in route_paths)

    def test_queue_service_can_execute(self):
        record = _rec(status="approved")
        assert AgentExecutionQueueService.can_execute(record) is True

    def test_queue_service_sanitize_exists(self):
        assert callable(AgentExecutionQueueService.sanitize_record_for_api)

    def test_sender_service_importable(self):
        from core.services.approved_execution_sender_service import (
            ApprovedExecutionSenderService,
        )

        assert ApprovedExecutionSenderService is not None

    def test_signal_service_still_works(self):
        from core.services.lead_signal_service import LeadSignalService

        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"

    def test_orchestrator_still_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        mem = {
            "followup_enabled": True,
            "memory_data": {},
            "lead_temperature": "warm",
            "telegram_user_id": 1,
        }
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"
