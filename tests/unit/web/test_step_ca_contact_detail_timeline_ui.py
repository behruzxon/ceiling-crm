"""Tests for Step CA — Contact Detail Timeline Premium UI."""
from __future__ import annotations
from pathlib import Path

def _d():
    return Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")


class TestHeader:
    def test_back_link(self):
        assert "/crm" in _d() and "CRM Inbox" in _d()
    def test_contact_name(self):
        assert "first_name" in _d()
    def test_username(self):
        assert "username" in _d()
    def test_telegram_id(self):
        assert "telegram_user_id" in _d()
    def test_status_badge(self):
        assert "vp-badge" in _d() and "lead_status" in _d()
    def test_temperature_badge(self):
        assert "temperature" in _d()
    def test_score(self):
        assert "lead_score" in _d()
    def test_hero_card(self):
        assert "contact-hero" in _d()


class TestSLAHero:
    def test_sla_badge(self):
        assert "slaBadge" in _d()
    def test_sla_text(self):
        assert "slaStatusText" in _d()
    def test_next_action(self):
        assert "nextActionText" in _d()
    def test_sla_label(self):
        assert "SLA holati" in _d()


class TestCustomer360:
    def test_phone(self):
        assert "Telefon" in _d()
    def test_district(self):
        assert "Tuman" in _d()
    def test_area(self):
        assert "Maydon" in _d()
    def test_ceiling_type(self):
        assert "Potolok turi" in _d()
    def test_source(self):
        assert "Manba" in _d()
    def test_created(self):
        assert "Yaratilgan" in _d()
    def test_unknown_state(self):
        assert "Kiritilmagan" in _d()
    def test_profile_field_class(self):
        assert "profile-field" in _d()


class TestChecklist:
    def test_container(self):
        assert "operatorChecklist" in _d()
    def test_progress(self):
        assert "checklist-progress" in _d()
    def test_phone_item(self):
        c = _d()
        assert "Telefon" in c and "checklist-item" in c
    def test_area_item(self):
        assert "Maydon" in _d()
    def test_district_item(self):
        assert "Tuman" in _d()
    def test_ceiling_item(self):
        assert "Potolok turi" in _d()
    def test_status_item(self):
        assert "Status" in _d()
    def test_done_class(self):
        assert "checklist-done" in _d()


class TestTimeline:
    def test_container(self):
        assert "chatTimeline" in _d()
    def test_timeline_class(self):
        assert "timeline" in _d()
    def test_user_class(self):
        assert "timeline-item-user" in _d()
    def test_bot_class(self):
        assert "timeline-item-bot" in _d()
    def test_operator_class(self):
        assert "timeline-item-operator" in _d()
    def test_meta(self):
        assert "timeline-meta" in _d()
    def test_text(self):
        assert "timeline-text" in _d()
    def test_timestamp(self):
        assert "created_at" in _d()
    def test_sender_badge(self):
        assert "sender_type" in _d()
    def test_empty_state(self):
        assert "Xabarlar hali yo'q" in _d()
    def test_message_count(self):
        assert "xabar" in _d()


class TestReply:
    def test_section(self):
        assert "operatorReplySection" in _d()
    def test_disabled_notice(self):
        assert "replyDisabledNotice" in _d()
    def test_textarea(self):
        assert "replyTextarea" in _d()
    def test_vp_textarea(self):
        assert "vp-textarea" in _d()
    def test_preview_btn(self):
        assert "previewBtn" in _d()
    def test_send_btn(self):
        assert "sendBtn" in _d()
    def test_blockers(self):
        assert "replyBlockers" in _d()
    def test_warnings(self):
        assert "replyWarnings" in _d()
    def test_confirm_warn(self):
        assert "replyConfirmWarn" in _d()
    def test_telegram_warning(self):
        assert "real mijozga" in _d()


class TestNotesTagsTasks:
    def test_notes(self):
        assert "notesSection" in _d()
    def test_note_input(self):
        assert "noteInput" in _d()
    def test_tags(self):
        assert "tagsSection" in _d()
    def test_reply_audit(self):
        assert "replyAuditSection" in _d()


class TestResponsive:
    def test_no_300px_fixed(self):
        assert "300px 1fr" not in _d()
    def test_responsive_grid(self):
        assert "contact-grid" in _d()
    def test_media_1024(self):
        assert "1024px" in _d()
    def test_media_768(self):
        assert "768px" in _d()
    def test_sidebar_order(self):
        assert "order: -1" in _d()


class TestDesignSystem:
    def test_vp_card(self):
        assert "vp-card" in _d()
    def test_vp_btn(self):
        assert "vp-btn" in _d()
    def test_vp_alert(self):
        assert "vp-alert" in _d()
    def test_vp_badge(self):
        assert "vp-badge" in _d()


class TestSafety:
    def test_no_innerhtml(self):
        assert "innerHTML" not in _d()
    def test_textcontent(self):
        assert "textContent" in _d()
    def test_no_token(self):
        c = _d()
        assert "sk-" not in c
        assert "session_id_hash" not in c
    def test_no_alert_saqlandi(self):
        assert "alert('Saqlandi')" not in _d()
