"""Integration tests for Step CA — Contact Detail Timeline flow."""
from __future__ import annotations
from pathlib import Path


class TestRendering:
    def test_page_renders(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "contact-grid" in c
    def test_timeline_events(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "timeline-item-user" in c
        assert "timeline-item-bot" in c
        assert "timeline-item-operator" in c
    def test_empty_timeline(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "Xabarlar hali yo'q" in c


class TestSLA:
    def test_sla_card(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "slaBadge" in c
    def test_next_action(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "nextActionText" in c


class TestReplyPreserved:
    def test_reply_section(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "operatorReplySection" in c
    def test_disabled_notice(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "o'chirilgan" in c.lower()


class TestMobile:
    def test_responsive(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "1024px" in c
        assert "768px" in c
    def test_no_fixed_300(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "300px 1fr" not in c


class TestNoSend:
    def test_no_telegram_import(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "aiogram" not in c
    def test_no_send_message(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "send_message" not in c


class TestNoTokenLeak:
    def test_no_secret(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "sk-" not in c
        assert "session_id_hash" not in c


class TestSmoke:
    def test_web(self):
        from apps.web.main import app
        assert app is not None
    def test_api(self):
        from apps.api.main import app
        assert app is not None
