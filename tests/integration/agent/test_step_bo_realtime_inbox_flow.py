"""Integration tests for Step BO — Realtime Inbox flow."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


class TestLiveSummaryBuild:
    def _contact(self, **kw):
        base = {
            "id": 1, "contact_name": "Test", "lead_status": "active",
            "temperature": "warm", "last_message_direction": "inbound",
            "last_message_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "last_intent": None, "metadata_json": None,
        }
        base.update(kw)
        return base

    def test_inbound_creates_unanswered(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService
        s = CRMRealtimeInboxService.build_live_summary([self._contact()])
        assert s.unanswered_count >= 1

    def test_stopped_not_alerted(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService
        s = CRMRealtimeInboxService.build_live_summary([self._contact(lead_status="stopped")])
        assert s.unanswered_count == 0

    def test_outbound_cleared(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService
        s = CRMRealtimeInboxService.build_live_summary([
            self._contact(last_message_direction="outbound"),
        ])
        assert s.unanswered_count == 0


class TestPulseDetection:
    def test_new_critical_pulses(self):
        from core.services.crm_realtime_inbox_service import (
            CRMRealtimeInboxService,
            LiveInboxSummary,
        )
        prev = {"critical_count": 0}
        curr = LiveInboxSummary(critical_count=2)
        assert CRMRealtimeInboxService.should_pulse(prev, curr) is True

    def test_same_no_pulse(self):
        from core.services.crm_realtime_inbox_service import (
            CRMRealtimeInboxService,
            LiveInboxSummary,
        )
        prev = {"critical_count": 2}
        curr = LiveInboxSummary(critical_count=2)
        assert CRMRealtimeInboxService.should_pulse(prev, curr) is False


class TestNoSendOccurs:
    def test_no_telegram_in_service(self):
        import inspect

        import core.services.crm_realtime_inbox_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src

    def test_no_openai_in_service(self):
        import inspect

        import core.services.crm_realtime_inbox_service as mod
        src = inspect.getsource(mod)
        assert "openai" not in src.lower()


class TestNoTokenLeak:
    def test_token_redacted(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService
        assert "sk-" not in CRMRealtimeInboxService._safe_text("sk-secret123")

    def test_phone_redacted(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService
        assert "+998" not in CRMRealtimeInboxService._safe_text("+998901234567 yozdi")


class TestSmoke:
    def test_api(self):
        from apps.api.main import app
        assert app is not None

    def test_web(self):
        from apps.web.main import app
        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None

    def test_crm_page_template(self):
        from pathlib import Path
        content = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "setInterval" in content
        assert "live-summary" in content
