"""Integration tests for Step BR — CRM Contact Merge flow."""
from __future__ import annotations


def _c(**kw):
    base = {"id": 1, "telegram_user_id": None, "telegram_chat_id": None,
            "phone": None, "username": None, "first_name": None,
            "lead_status": "new", "lead_score": 0, "temperature": None,
            "merge_status": "active", "metadata_json": None, "data_quality_score": 0}
    base.update(kw)
    return base


class TestDuplicateDetection:
    def test_phone_detected(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        contacts = [_c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567")]
        result = CRMContactMergeService.find_duplicate_candidates(contacts)
        assert len(result) == 1
        assert result[0].confidence == 95

    def test_username_name_detected(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        contacts = [_c(id=1, username="ali", first_name="Ali"), _c(id=2, username="ali", first_name="Ali")]
        result = CRMContactMergeService.find_duplicate_candidates(contacts, min_confidence=70)
        assert len(result) == 1


class TestMergePreviewFlow:
    def test_preview_shows_plan(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        source = _c(id=1, phone="+998901234567", first_name="Ali")
        target = _c(id=2, phone="+998901234567", first_name="")
        p = CRMContactMergeService.build_merge_preview(source, target, merge_enabled=True)
        assert p.allowed
        assert p.plan["keep_phone"] == "+998901234567"
        assert p.plan["keep_name"] == "Ali"


class TestMergeDisabledFlow:
    def test_disabled_no_mutation(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        r = CRMContactMergeService.validate_merge(_c(id=1), _c(id=2), merge_enabled=False, confirm=True)
        assert not r.ok
        assert "disabled" in r.error


class TestMergeEnabledFlow:
    def test_merge_moves_plan(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        source = _c(id=1, phone="+998901234567", lead_score=80, temperature="hot")
        target = _c(id=2, phone="+998901234567", lead_score=30, temperature="cold")
        r = CRMContactMergeService.validate_merge(source, target, merge_enabled=True, confirm=True)
        assert r.ok

    def test_source_marked_merged(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        d = CRMContactMergeService.build_source_merged_dict(2)
        assert d["merge_status"] == "merged"
        assert d["merged_into_contact_id"] == 2


class TestMergeAuditFlow:
    def test_audit_written(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        a = CRMContactMergeService.build_merge_audit(1, 2, status="merged", confidence=95)
        assert a["status"] == "merged"
        assert a["source_contact_id"] == 1

    def test_snapshot_sanitized(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        a = CRMContactMergeService.build_merge_audit(
            1, 2, source_snapshot={"phone": "+998901234567", "id": 1},
        )
        assert "*" in a["before_source_json"]["phone"]


class TestMergedExcluded:
    def test_merged_not_in_candidates(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        contacts = [_c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567", merge_status="merged")]
        assert CRMContactMergeService.find_duplicate_candidates(contacts) == []


class TestStoppedCandidate:
    def test_stopped_can_be_candidate(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        contacts = [_c(id=1, phone="+998901234567", lead_status="stopped"), _c(id=2, phone="+998901234567")]
        result = CRMContactMergeService.find_duplicate_candidates(contacts)
        assert len(result) == 1


class TestNoSendOccurs:
    def test_no_telegram(self):
        import inspect
        import core.services.crm_contact_merge_service as mod
        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src


class TestNoTokenLeak:
    def test_snapshot_no_token(self):
        from core.services.crm_contact_merge_service import CRMContactMergeService
        s = CRMContactMergeService.sanitize_snapshot({"note": "sk-secret123"})
        assert "sk-" not in s["note"]


class TestSmoke:
    def test_api(self):
        from apps.api.main import app
        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
