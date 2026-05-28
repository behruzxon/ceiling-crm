"""Step 11 — Operator digest integration flow.

In-memory pipeline: build handoff + missed-lead rows, run the digest
service, run the format_digest_text renderer, confirm the API module
and web template surface the result. No Telegram, no OpenAI, no DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.services.crm_operator_digest_service import (
    SEVERITY_GREEN,
    SEVERITY_RED,
    SEVERITY_YELLOW,
    build_digest,
    format_digest_text,
)

NOW = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)


@dataclass
class HF:
    status: str = "open"
    priority: str = "normal"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    contacted_at: datetime | None = None
    resolved_at: datetime | None = None
    assigned_at: datetime | None = None
    assigned_to_admin_id: str | None = None


@dataclass
class ML:
    severity: str = "high"
    reason: str = "operator_waiting"


class TestEndToEndFlow:
    def test_create_handoff_and_missed_then_build_digest(self) -> None:
        handoffs = [
            HF(status="open", priority="urgent", created_at=NOW - timedelta(hours=1)),
            HF(status="waiting_phone", created_at=NOW - timedelta(minutes=30)),
            HF(
                status="assigned",
                priority="high",
                assigned_at=NOW - timedelta(hours=2),
                assigned_to_admin_id="op-1",
            ),
        ]
        missed = [ML(severity="critical", reason="hot_unanswered")]
        result = build_digest(now=NOW, handoffs=handoffs, missed_leads=missed)

        assert result.summary.total_open == 1
        assert result.summary.waiting_phone == 1
        assert result.summary.assigned == 1
        assert result.summary.urgent_open == 1
        assert result.summary.high_open == 1
        assert result.summary.critical_missed == 1
        assert result.summary.severity == SEVERITY_RED

    def test_quiet_state_renders_green_text(self) -> None:
        result = build_digest(now=NOW, handoffs=[], missed_leads=[])
        text = format_digest_text(result)
        assert SEVERITY_GREEN.upper() in text

    def test_yellow_state_renders(self) -> None:
        result = build_digest(
            now=NOW,
            handoffs=[HF(status="open", priority="high")],
            missed_leads=[],
        )
        assert result.summary.severity == SEVERITY_YELLOW
        text = format_digest_text(result)
        assert "YELLOW" in text


class TestApiPreview:
    """API module is importable and re-exports the right symbols."""

    def test_api_module_imports(self) -> None:
        from apps.api.routes import admin_crm_operator_digest as mod

        assert mod.operator_digest_daily is not None
        assert mod.operator_digest_preview is not None

    def test_api_registered_in_main(self) -> None:
        src = Path("apps/api/main.py").read_text(encoding="utf-8")
        assert "admin_crm_operator_digest_router" in src


class TestWebShell:
    """The web template that wraps the digest card renders cleanly."""

    def test_template_exists(self) -> None:
        template = Path("apps/web/templates/crm_handoffs.html")
        assert template.exists()

    def test_template_includes_digest_card(self) -> None:
        src = Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")
        assert "Daily Operator Digest" in src

    def test_template_calls_loader_on_load(self) -> None:
        src = Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")
        assert "loadOperatorDigest" in src

    def test_template_no_send_button(self) -> None:
        src = Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")
        assert "Yuborish (disabled)" in src


class TestSafetyGuarantees:
    def test_no_telegram_send_in_service(self) -> None:
        src = Path("core/services/crm_operator_digest_service.py").read_text(encoding="utf-8")
        assert "import aiogram" not in src
        assert "from aiogram" not in src
        assert "send_message" not in src

    def test_no_openai_call_in_service(self) -> None:
        src = Path("core/services/crm_operator_digest_service.py").read_text(encoding="utf-8")
        assert "import openai" not in src
        assert "from openai" not in src

    def test_no_phone_leak_in_rendered_text(self) -> None:
        result = build_digest(
            now=NOW,
            handoffs=[HF(status="open", priority="urgent")],
            missed_leads=[],
        )
        text = format_digest_text(result)
        import re

        assert not re.search(r"\+?\d{7,}", text)

    def test_no_token_in_rendered_text(self) -> None:
        result = build_digest(now=NOW, handoffs=[], missed_leads=[])
        text = format_digest_text(result)
        assert "sk-" not in text
        assert "Bearer " not in text

    def test_no_fake_eta_in_rendered_text(self) -> None:
        result = build_digest(now=NOW, handoffs=[HF(status="open")], missed_leads=[])
        text = format_digest_text(result)
        assert "ETA:" not in text


class TestRegressionAdjacentSteps:
    """Sanity checks that Step 8/9 still import cleanly."""

    def test_step_8_take_endpoint(self) -> None:
        from apps.api.routes.admin_crm_handoffs import take_handoff

        assert callable(take_handoff)

    def test_step_9_service_class(self) -> None:
        from core.services.crm_operator_handoff_service import CRMOperatorHandoffService

        assert CRMOperatorHandoffService is not None

    def test_step_9_job_callable(self) -> None:
        from apps.scheduler.jobs.crm_handoff_expire_jobs import run_handoff_expire_job

        assert callable(run_handoff_expire_job)


class TestStateAcrossSeverities:
    def test_green(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[])
        assert r.summary.severity == "green"

    def test_yellow(self) -> None:
        r = build_digest(now=NOW, handoffs=[HF(status="open", priority="high")], missed_leads=[])
        assert r.summary.severity == "yellow"

    def test_red(self) -> None:
        r = build_digest(now=NOW, handoffs=[], missed_leads=[ML(severity="critical")])
        assert r.summary.severity == "red"
