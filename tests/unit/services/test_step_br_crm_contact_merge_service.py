"""Tests for Step BR — CRMContactMergeService."""
from __future__ import annotations

from core.services.crm_contact_merge_service import CRMContactMergeService

svc = CRMContactMergeService


def _c(**kw):
    base = {"id": 1, "telegram_user_id": None, "telegram_chat_id": None,
            "phone": None, "username": None, "first_name": None,
            "lead_status": "new", "lead_score": 0, "temperature": None,
            "merge_status": "active", "metadata_json": None, "data_quality_score": 0}
    base.update(kw)
    return base


class TestConfidence:
    def test_same_telegram_id_100(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, telegram_user_id=123), _c(id=2, telegram_user_id=123)) == 100

    def test_same_chat_id_95(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, telegram_chat_id=456), _c(id=2, telegram_chat_id=456)) == 95

    def test_same_phone_95(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567")) == 95

    def test_phone_last_9_85(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, phone="+998901234567"), _c(id=2, phone="901234567")) == 85

    def test_username_and_name_80(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, username="ali", first_name="Ali"), _c(id=2, username="ali", first_name="Ali")) == 80

    def test_username_only_60(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, username="ali"), _c(id=2, username="ali")) == 60

    def test_name_only_weak_30(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, first_name="Ali"), _c(id=2, first_name="Ali")) == 30

    def test_no_match_0(self):
        assert svc.calculate_duplicate_confidence(_c(id=1), _c(id=2)) == 0

    def test_same_id_0(self):
        assert svc.calculate_duplicate_confidence(_c(id=1), _c(id=1)) == 0

    def test_merged_excluded_0(self):
        assert svc.calculate_duplicate_confidence(_c(id=1, merge_status="merged"), _c(id=2, telegram_user_id=123)) == 0


class TestReasons:
    def test_same_telegram(self):
        r = svc.build_duplicate_reasons(_c(telegram_user_id=1), _c(telegram_user_id=1))
        assert "same_telegram_user_id" in r

    def test_same_phone(self):
        r = svc.build_duplicate_reasons(_c(phone="+998901234567"), _c(phone="+998901234567"))
        assert "same_phone" in r

    def test_same_phone_last_9(self):
        r = svc.build_duplicate_reasons(_c(phone="+998901234567"), _c(phone="901234567"))
        assert "same_phone_last_9" in r

    def test_same_username(self):
        r = svc.build_duplicate_reasons(_c(username="ali"), _c(username="ali"))
        assert "same_username" in r

    def test_same_first_name(self):
        r = svc.build_duplicate_reasons(_c(first_name="Ali"), _c(first_name="Ali"))
        assert "same_first_name" in r


class TestFindCandidates:
    def test_empty(self):
        assert svc.find_duplicate_candidates([]) == []

    def test_finds_duplicates(self):
        contacts = [_c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567")]
        result = svc.find_duplicate_candidates(contacts)
        assert len(result) == 1
        assert result[0].confidence == 95

    def test_merged_excluded(self):
        contacts = [_c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567", merge_status="merged")]
        assert svc.find_duplicate_candidates(contacts) == []

    def test_limit(self):
        contacts = [_c(id=i, telegram_user_id=1) for i in range(10)]
        result = svc.find_duplicate_candidates(contacts, limit=3)
        assert len(result) <= 3

    def test_min_confidence_filter(self):
        contacts = [_c(id=1, username="ali"), _c(id=2, username="ali")]
        assert len(svc.find_duplicate_candidates(contacts, min_confidence=80)) == 0
        assert len(svc.find_duplicate_candidates(contacts, min_confidence=50)) == 1


class TestMergePlan:
    def test_target_keeps_phone(self):
        plan = svc.build_merge_plan(_c(phone="+998111"), _c(phone="+998222"))
        assert plan["keep_phone"] == "+998222"

    def test_source_fills_missing_phone(self):
        plan = svc.build_merge_plan(_c(phone="+998111"), _c(phone=None))
        assert plan["keep_phone"] == "+998111"

    def test_highest_score(self):
        plan = svc.build_merge_plan(_c(lead_score=50), _c(lead_score=30))
        assert plan["keep_score"] == 50

    def test_hottest_temperature(self):
        plan = svc.build_merge_plan(_c(temperature="hot"), _c(temperature="cold"))
        assert plan["keep_temperature"] == "hot"

    def test_priority_status(self):
        plan = svc.build_merge_plan(_c(lead_status="new"), _c(lead_status="hot"))
        assert plan["keep_status"] == "hot"

    def test_merge_tags_true(self):
        plan = svc.build_merge_plan(_c(), _c())
        assert plan["merge_tags"] is True

    def test_merge_messages_true(self):
        plan = svc.build_merge_plan(_c(), _c())
        assert plan["merge_messages"] is True

    def test_source_soft_mark(self):
        plan = svc.build_merge_plan(_c(), _c())
        assert plan["source_action"] == "soft_mark"


class TestMergePreview:
    def test_same_id_blocked(self):
        p = svc.build_merge_preview(_c(id=1), _c(id=1))
        assert not p.allowed
        assert "source_equals_target" in p.blockers

    def test_source_merged_blocked(self):
        p = svc.build_merge_preview(_c(id=1, merge_status="merged"), _c(id=2))
        assert "source_already_merged" in p.blockers

    def test_target_merged_blocked(self):
        p = svc.build_merge_preview(_c(id=1), _c(id=2, merge_status="merged"))
        assert "target_already_merged" in p.blockers

    def test_different_telegram_ids_blocked(self):
        p = svc.build_merge_preview(_c(id=1, telegram_user_id=111), _c(id=2, telegram_user_id=222))
        assert "different_telegram_user_ids" in p.blockers

    def test_different_phones_blocked(self):
        p = svc.build_merge_preview(_c(id=1, phone="+998111111111"), _c(id=2, phone="+998222222222"))
        assert any("different_phones" in b for b in p.blockers)

    def test_low_confidence_blocked(self):
        p = svc.build_merge_preview(_c(id=1), _c(id=2), min_confidence=80)
        assert any("low_confidence" in b for b in p.blockers)

    def test_allowed_with_phone_match(self):
        p = svc.build_merge_preview(
            _c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567"),
            merge_enabled=True,
        )
        assert p.allowed
        assert p.confidence == 95

    def test_merge_disabled_warning(self):
        p = svc.build_merge_preview(_c(id=1, telegram_user_id=1), _c(id=2, telegram_user_id=1), merge_enabled=False)
        assert "merge_disabled_preview_only" in p.warnings

    def test_terminal_status_warning(self):
        p = svc.build_merge_preview(_c(id=1, telegram_user_id=1, lead_status="stopped"), _c(id=2, telegram_user_id=1))
        assert any("terminal" in w for w in p.warnings)


class TestValidateMerge:
    def test_disabled(self):
        r = svc.validate_merge(_c(id=1), _c(id=2), merge_enabled=False)
        assert not r.ok
        assert "disabled" in r.error

    def test_no_confirm(self):
        r = svc.validate_merge(_c(id=1), _c(id=2), merge_enabled=True, confirm=False)
        assert not r.ok
        assert "confirmation" in r.error

    def test_success(self):
        r = svc.validate_merge(
            _c(id=1, phone="+998901234567"), _c(id=2, phone="+998901234567"),
            merge_enabled=True, confirm=True,
        )
        assert r.ok


class TestSourceMergedDict:
    def test_build(self):
        d = svc.build_source_merged_dict(target_contact_id=2)
        assert d["merged_into_contact_id"] == 2
        assert d["merge_status"] == "merged"
        assert d["merged_at"] != ""


class TestMergeAudit:
    def test_build_preview(self):
        a = svc.build_merge_audit(1, 2, actor_admin_id="admin1", status="previewed", confidence=95)
        assert a["source_contact_id"] == 1
        assert a["status"] == "previewed"

    def test_build_merged(self):
        a = svc.build_merge_audit(1, 2, status="merged", confidence=95)
        assert a["status"] == "merged"

    def test_snapshot_sanitized(self):
        a = svc.build_merge_audit(1, 2, source_snapshot={"phone": "+998901234567", "id": 1})
        assert "*" in a["before_source_json"]["phone"]


class TestDataQualitySummary:
    def test_empty(self):
        s = svc.build_data_quality_summary([])
        assert s.total_contacts == 0

    def test_counts(self):
        contacts = [_c(id=1, phone="+998901234567", first_name="Ali"), _c(id=2, phone=None, first_name=None)]
        s = svc.build_data_quality_summary(contacts)
        assert s.total_contacts == 2
        assert s.missing_phone == 1
        assert s.missing_name == 1

    def test_merged_counted(self):
        contacts = [_c(id=1), _c(id=2, merge_status="merged")]
        s = svc.build_data_quality_summary(contacts)
        assert s.merged_contacts == 1
        assert s.active_contacts == 1


class TestSanitizeSnapshot:
    def test_none(self):
        assert svc.sanitize_snapshot(None) is None

    def test_phone_masked(self):
        s = svc.sanitize_snapshot({"phone": "+998901234567"})
        assert "*" in s["phone"]

    def test_token_redacted(self):
        s = svc.sanitize_snapshot({"note": "sk-secret123"})
        assert "sk-" not in s["note"]

    def test_no_session_hash(self):
        s = svc.sanitize_snapshot({"session_id_hash": "abc", "id": 1})
        assert "session_id_hash" not in s


class TestImmutability:
    def test_candidate_frozen(self):
        import pytest

        from core.services.crm_contact_merge_service import DuplicateCandidate
        c = DuplicateCandidate()
        with pytest.raises(AttributeError):
            c.confidence = 5  # type: ignore[misc]

    def test_preview_frozen(self):
        import pytest

        from core.services.crm_contact_merge_service import MergePreview
        p = MergePreview()
        with pytest.raises(AttributeError):
            p.allowed = True  # type: ignore[misc]

    def test_result_frozen(self):
        import pytest

        from core.services.crm_contact_merge_service import MergeResult
        r = MergeResult()
        with pytest.raises(AttributeError):
            r.ok = True  # type: ignore[misc]

    def test_summary_frozen(self):
        import pytest

        from core.services.crm_contact_merge_service import DataQualitySummary
        s = DataQualitySummary()
        with pytest.raises(AttributeError):
            s.total_contacts = 5  # type: ignore[misc]
