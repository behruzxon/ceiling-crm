"""Integration tests for Step BS — Campaign Draft flow."""
from __future__ import annotations


def _c(**kw):
    base = {"id": 1, "lead_status": "active", "temperature": "warm", "lead_score": 30,
            "phone": None, "first_name": "Ali", "username": "ali", "merge_status": "active",
            "marketing_allowed": True, "metadata_json": {}}
    base.update(kw)
    return base


class TestSegmentFiltering:
    def test_hot_lead(self):
        from core.services.crm_campaign_service import CRMCampaignService
        contacts = [_c(id=1, temperature="hot"), _c(id=2, temperature="cold")]
        eligible, _ = CRMCampaignService.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 1

    def test_stopped_excluded(self):
        from core.services.crm_campaign_service import CRMCampaignService
        contacts = [_c(id=1, lead_status="stopped", temperature="hot")]
        eligible, exc = CRMCampaignService.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 0
        assert exc == 1

    def test_marketing_false_excluded(self):
        from core.services.crm_campaign_service import CRMCampaignService
        contacts = [_c(id=1, marketing_allowed=False, temperature="hot")]
        eligible, exc = CRMCampaignService.filter_recipients(contacts, "hot_leads")
        assert len(eligible) == 0


class TestDraftFlow:
    def test_create_draft(self):
        from core.services.crm_campaign_service import CRMCampaignService
        d = CRMCampaignService.build_draft_dict("Test", "hot_leads", "Salom!", created_by="admin1")
        assert d["name"] == "Test"
        assert d["status"] == "draft"

    def test_safety_blocks_token(self):
        from core.services.crm_campaign_service import CRMCampaignService
        v = CRMCampaignService.validate_draft("Test", "hot_leads", "sk-secret123")
        assert not v.ok

    def test_safety_send_disabled(self):
        from core.services.crm_campaign_service import CRMCampaignService
        s = CRMCampaignService.check_safety(10, "Salom!", send_enabled=False)
        assert "send_disabled" in s.reasons
        assert not s.send_enabled


class TestAudit:
    def test_audit_written(self):
        from core.services.crm_campaign_service import CRMCampaignService
        a = CRMCampaignService.build_audit_entry(
            campaign_id=1, actor_admin_id="admin1", action="campaign.created",
        )
        assert a["action"] == "campaign.created"


class TestNoSend:
    def test_no_telegram(self):
        import inspect

        import core.services.crm_campaign_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src

    def test_no_email(self):
        import inspect

        import core.services.crm_campaign_service as mod
        src = inspect.getsource(mod)
        assert "smtp" not in src.lower()


class TestNoTokenLeak:
    def test_message_sanitized(self):
        from core.services.crm_campaign_service import CRMCampaignService
        assert "sk-" not in CRMCampaignService.sanitize_message("sk-secret123")


class TestSmoke:
    def test_api(self):
        from apps.api.main import app
        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
