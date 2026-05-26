"""Tests for Step BS — CRMCampaignService."""
from __future__ import annotations
from core.services.crm_campaign_service import CRMCampaignService

svc = CRMCampaignService

def _c(**kw):
    base = {"id": 1, "lead_status": "active", "temperature": "warm", "lead_score": 30,
            "phone": None, "first_name": "Ali", "username": "ali", "merge_status": "active",
            "marketing_allowed": True, "metadata_json": {}}
    base.update(kw)
    return base


class TestSegments:
    def test_list(self):
        segs = svc.get_available_segments()
        assert len(segs) >= 10
        assert any(s.key == "hot_leads" for s in segs)

    def test_valid(self):
        assert svc.is_valid_segment("hot_leads")
        assert svc.is_valid_segment("price_interested")
        assert not svc.is_valid_segment("nonexistent")

    def test_info(self):
        info = svc.get_segment_info("hot_leads")
        assert info is not None
        assert info.key == "hot_leads"

    def test_info_invalid(self):
        assert svc.get_segment_info("bad") is None


class TestFilterRecipients:
    def test_hot_leads(self):
        contacts = [_c(id=1, temperature="hot"), _c(id=2, temperature="cold")]
        eligible, exc = svc.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 1
        assert eligible[0]["id"] == 1

    def test_excludes_stopped(self):
        contacts = [_c(id=1, lead_status="stopped", temperature="hot")]
        eligible, exc = svc.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 0
        assert exc == 1

    def test_excludes_merged(self):
        contacts = [_c(id=1, merge_status="merged", temperature="hot")]
        eligible, exc = svc.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 0

    def test_excludes_marketing_disabled(self):
        contacts = [_c(id=1, marketing_allowed=False, temperature="hot")]
        eligible, exc = svc.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 0

    def test_price_interested(self):
        contacts = [_c(id=1, lead_status="price_interested")]
        eligible, _ = svc.filter_recipients(contacts, "price_interested")
        assert len(eligible) == 1

    def test_phone_shared(self):
        contacts = [_c(id=1, phone="+998901234567"), _c(id=2)]
        eligible, _ = svc.filter_recipients(contacts, "phone_shared")
        assert len(eligible) == 1

    def test_all_active(self):
        contacts = [_c(id=1), _c(id=2, lead_status="stopped")]
        eligible, exc = svc.filter_recipients(contacts, "all_active")
        assert len(eligible) == 1


class TestPreviewRecipients:
    def test_preview(self):
        contacts = [_c(id=1, temperature="hot")]
        result = svc.preview_recipients(contacts, "hot_leads")
        assert result["total_eligible"] == 1
        assert len(result["preview"]) == 1
        assert result["preview"][0]["contact_id"] == 1

    def test_max_preview(self):
        contacts = [_c(id=i, temperature="hot") for i in range(20)]
        result = svc.preview_recipients(contacts, "hot_leads", max_preview=5)
        assert len(result["preview"]) == 5

    def test_empty(self):
        result = svc.preview_recipients([], "hot_leads")
        assert result["total_eligible"] == 0


class TestValidateDraft:
    def test_valid(self):
        r = svc.validate_draft("Test Campaign", "hot_leads", "Salom, yangi taklif!")
        assert r.ok

    def test_empty_name(self):
        r = svc.validate_draft("", "hot_leads", "text")
        assert not r.ok
        assert "name" in r.error

    def test_long_name(self):
        r = svc.validate_draft("x" * 201, "hot_leads", "text")
        assert not r.ok

    def test_invalid_segment(self):
        r = svc.validate_draft("Test", "bad_segment", "text")
        assert not r.ok
        assert "segment" in r.error

    def test_empty_message(self):
        r = svc.validate_draft("Test", "hot_leads", "")
        assert not r.ok

    def test_long_message(self):
        r = svc.validate_draft("Test", "hot_leads", "x" * 1001)
        assert not r.ok

    def test_token_blocked(self):
        r = svc.validate_draft("Test", "hot_leads", "sk-secret123 taklif")
        assert not r.ok
        assert "token" in r.error

    def test_bot_token_blocked(self):
        r = svc.validate_draft("Test", "hot_leads", "1234567890:ABCdefGhIjKlMnOpQrStUvWxYz12345678")
        assert not r.ok

    def test_phone_warning(self):
        r = svc.validate_draft("Test", "hot_leads", "+998901234567 ga qo'ng'iroq qiling")
        assert r.ok
        assert any("phone" in w for w in r.warnings)


class TestCheckSafety:
    def test_safe(self):
        r = svc.check_safety(10, "Salom!", send_enabled=True)
        assert r.status == "safe"
        assert r.allowed

    def test_send_disabled(self):
        r = svc.check_safety(10, "Salom!", send_enabled=False)
        assert "send_disabled" in r.reasons
        assert r.status == "warning"

    def test_no_recipients(self):
        r = svc.check_safety(0, "Salom!", send_enabled=True)
        assert "no_recipients" in r.reasons

    def test_empty_message(self):
        r = svc.check_safety(10, "", send_enabled=True)
        assert "empty_message" in r.reasons

    def test_token_in_message(self):
        r = svc.check_safety(10, "sk-secret123", send_enabled=True)
        assert "token_in_message" in r.reasons

    def test_large_list_warning(self):
        r = svc.check_safety(2000, "Salom!", send_enabled=True)
        assert "large_recipient_list" in r.reasons


class TestBuildDraftDict:
    def test_basic(self):
        d = svc.build_draft_dict("Test", "hot_leads", "Salom!", created_by="admin1")
        assert d["name"] == "Test"
        assert d["segment_key"] == "hot_leads"
        assert d["status"] == "draft"
        assert d["created_by"] == "admin1"

    def test_sanitizes_message(self):
        d = svc.build_draft_dict("Test", "hot_leads", "sk-secret123 taklif")
        assert "sk-" not in d["message_text"]


class TestBuildAuditEntry:
    def test_basic(self):
        a = svc.build_audit_entry(campaign_id=1, actor_admin_id="admin1", action="campaign.created")
        assert a["campaign_id"] == 1
        assert a["action"] == "campaign.created"

    def test_reason_sanitized(self):
        a = svc.build_audit_entry(reason="sk-secret error")
        assert "sk-" not in a["reason"]


class TestSanitizeMessage:
    def test_token(self):
        assert "sk-" not in svc.sanitize_message("sk-secret123")

    def test_bot_token(self):
        r = svc.sanitize_message("1234567890:ABCdefGhIjKlMnOpQrStUvWxYz12345678")
        assert "ABCdef" not in r

    def test_clean(self):
        assert svc.sanitize_message("Salom!") == "Salom!"


class TestStatuses:
    def test_draft_statuses(self):
        assert len(svc.get_draft_statuses()) == 5
        assert "draft" in svc.get_draft_statuses()

    def test_safety_statuses(self):
        assert len(svc.get_safety_statuses()) == 4
        assert "safe" in svc.get_safety_statuses()


class TestImmutability:
    def test_segment_frozen(self):
        import pytest
        from core.services.crm_campaign_service import SegmentInfo
        s = SegmentInfo()
        with pytest.raises(AttributeError):
            s.key = "x"  # type: ignore[misc]

    def test_safety_frozen(self):
        import pytest
        from core.services.crm_campaign_service import SafetyCheckResult
        r = SafetyCheckResult()
        with pytest.raises(AttributeError):
            r.status = "x"  # type: ignore[misc]

    def test_validation_frozen(self):
        import pytest
        from core.services.crm_campaign_service import DraftValidation
        r = DraftValidation()
        with pytest.raises(AttributeError):
            r.ok = True  # type: ignore[misc]
