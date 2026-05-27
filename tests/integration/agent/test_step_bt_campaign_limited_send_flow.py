"""Integration tests for Step BT — Campaign Limited Send flow."""
from __future__ import annotations


def _campaign(**kw):
    base = {"id": 1, "status": "approved", "message_text": "Salom {first_name}!"}
    base.update(kw)
    return base

def _contact(**kw):
    base = {"id": 1, "telegram_user_id": 123, "telegram_chat_id": 123,
            "first_name": "Ali", "username": "ali", "lead_status": "active",
            "merge_status": "active", "marketing_allowed": True,
            "followup_allowed": True, "metadata_json": {}}
    base.update(kw)
    return base


class TestSendDisabledBlocks:
    def test_blocked(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.validate_campaign_for_send(_campaign(), send_enabled=False)
        assert not r.allowed


class TestDryRunNoSend:
    def test_dry_run(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.dry_run(_campaign(), [_contact()])
        assert r.dry_run
        assert r.would_send == 1


class TestCanaryFlow:
    def test_canary_allows(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.validate_recipient(_contact(id=1), canary_enabled=True, canary_ids={1})
        assert r.eligible
        assert r.is_canary

    def test_non_canary_blocked(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.validate_recipient(_contact(id=2), canary_enabled=True, canary_ids={1})
        assert not r.eligible


class TestExclusionsAtSendTime:
    def test_stopped(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.validate_recipient(_contact(lead_status="stopped"))
        assert not r.eligible

    def test_marketing_false(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.validate_recipient(_contact(marketing_allowed=False))
        assert not r.eligible

    def test_duplicate(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        r = CRMCampaignSendService.validate_recipient(_contact(id=5), already_sent_ids={5})
        assert not r.eligible


class TestAttemptAudit:
    def test_attempt_created(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        a = CRMCampaignSendService.build_send_attempt(1, 2, status="proposed", batch_id="b1")
        assert a["campaign_id"] == 1
        assert a["status"] == "proposed"

    def test_sent_marked(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        d = CRMCampaignSendService.mark_attempt_sent(999)
        assert d["status"] == "sent"

    def test_failed_marked(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        d = CRMCampaignSendService.mark_attempt_failed("error")
        assert d["status"] == "failed"


class TestNoRealTelegram:
    def test_no_telegram_in_service(self):
        import inspect

        import core.services.crm_campaign_send_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src

    def test_no_send_message_call(self):
        import inspect

        import core.services.crm_campaign_send_service as mod
        src = inspect.getsource(mod)
        assert "bot.send_message" not in src


class TestNoTokenLeak:
    def test_error_sanitized(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        assert "sk-" not in CRMCampaignSendService.redact_error("sk-secret123")

    def test_result_sanitized(self):
        from core.services.crm_campaign_send_service import CRMCampaignSendService
        d = CRMCampaignSendService.sanitize_send_result({"note": "sk-secret"})
        assert "sk-" not in d["note"]


class TestSmoke:
    def test_api(self):
        from apps.api.main import app
        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
