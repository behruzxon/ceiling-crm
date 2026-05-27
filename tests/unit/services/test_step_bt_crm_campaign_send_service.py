"""Tests for Step BT — CRMCampaignSendService."""

from __future__ import annotations

from core.services.crm_campaign_send_service import CRMCampaignSendService

svc = CRMCampaignSendService


def _campaign(**kw):
    base = {"id": 1, "status": "approved", "message_text": "Salom {first_name}!"}
    base.update(kw)
    return base


def _contact(**kw):
    base = {
        "id": 1,
        "telegram_user_id": 123,
        "telegram_chat_id": 123,
        "first_name": "Ali",
        "username": "ali",
        "lead_status": "active",
        "merge_status": "active",
        "marketing_allowed": True,
        "followup_allowed": True,
        "metadata_json": {},
    }
    base.update(kw)
    return base


class TestValidateCampaign:
    def test_send_disabled(self):
        r = svc.validate_campaign_for_send(_campaign(), send_enabled=False)
        assert not r.allowed
        assert "send_disabled" in r.blockers

    def test_dry_run_only(self):
        r = svc.validate_campaign_for_send(_campaign(), send_enabled=True, dry_run_only=True)
        assert "dry_run_only" in r.blockers

    def test_unapproved(self):
        r = svc.validate_campaign_for_send(
            _campaign(status="draft"), send_enabled=True, dry_run_only=False
        )
        assert "campaign_not_approved" in r.blockers

    def test_no_confirm(self):
        r = svc.validate_campaign_for_send(
            _campaign(), send_enabled=True, dry_run_only=False, confirm=False
        )
        assert "confirmation_required" in r.blockers

    def test_empty_message(self):
        r = svc.validate_campaign_for_send(
            _campaign(message_text=""), send_enabled=True, dry_run_only=False, confirm=True
        )
        assert "empty_message" in r.blockers

    def test_token_blocked(self):
        r = svc.validate_campaign_for_send(
            _campaign(message_text="sk-secret123"),
            send_enabled=True,
            dry_run_only=False,
            confirm=True,
        )
        assert "token_in_message" in r.blockers

    def test_bot_token_blocked(self):
        r = svc.validate_campaign_for_send(
            _campaign(message_text="1234567890:ABCdefGhIjKlMnOpQrStUvWxYz12345678"),
            send_enabled=True,
            dry_run_only=False,
            confirm=True,
        )
        assert "bot_token_in_message" in r.blockers

    def test_long_message(self):
        r = svc.validate_campaign_for_send(
            _campaign(message_text="x" * 1001), send_enabled=True, dry_run_only=False, confirm=True
        )
        assert "message_too_long" in r.blockers

    def test_all_pass(self):
        r = svc.validate_campaign_for_send(
            _campaign(), send_enabled=True, dry_run_only=False, confirm=True
        )
        assert r.allowed


class TestValidateRecipient:
    def test_merged(self):
        r = svc.validate_recipient(_contact(merge_status="merged"))
        assert not r.eligible
        assert "merged" in r.blocked_reason

    def test_stopped(self):
        r = svc.validate_recipient(_contact(lead_status="stopped"))
        assert not r.eligible

    def test_lost(self):
        r = svc.validate_recipient(_contact(lead_status="lost"))
        assert not r.eligible

    def test_marketing_false(self):
        r = svc.validate_recipient(_contact(marketing_allowed=False))
        assert not r.eligible
        assert "marketing" in r.blocked_reason

    def test_followup_false(self):
        r = svc.validate_recipient(_contact(followup_allowed=False))
        assert not r.eligible

    def test_opted_out(self):
        r = svc.validate_recipient(_contact(metadata_json={"stop_request": True}))
        assert not r.eligible
        assert "opted_out" in r.blocked_reason

    def test_no_telegram_id(self):
        r = svc.validate_recipient(_contact(telegram_user_id=None, telegram_chat_id=None))
        assert not r.eligible
        assert "no_telegram" in r.blocked_reason

    def test_duplicate_send(self):
        r = svc.validate_recipient(_contact(id=5), already_sent_ids={5})
        assert not r.eligible
        assert "duplicate" in r.blocked_reason

    def test_canary_allows(self):
        r = svc.validate_recipient(_contact(id=1), canary_enabled=True, canary_ids={1})
        assert r.eligible
        assert r.is_canary

    def test_canary_blocks_non_canary(self):
        r = svc.validate_recipient(_contact(id=2), canary_enabled=True, canary_ids={1})
        assert not r.eligible
        assert "not_in_canary" in r.blocked_reason

    def test_eligible(self):
        r = svc.validate_recipient(_contact())
        assert r.eligible


class TestRevalidateMessage:
    def test_clean(self):
        r = svc.revalidate_message_safety("Salom!")
        assert r.allowed

    def test_token(self):
        r = svc.revalidate_message_safety("sk-secret123")
        assert not r.allowed

    def test_empty(self):
        r = svc.revalidate_message_safety("")
        assert not r.allowed


class TestPersonalizedMessage:
    def test_first_name(self):
        msg = svc.build_personalized_message("Salom {first_name}!", _contact(first_name="Ali"))
        assert "Ali" in msg

    def test_username(self):
        msg = svc.build_personalized_message("@{username}", _contact(username="ali123"))
        assert "ali123" in msg

    def test_missing_placeholder(self):
        msg = svc.build_personalized_message("Salom {first_name}!", _contact(first_name=None))
        assert "None" not in msg

    def test_no_none_leak(self):
        msg = svc.build_personalized_message("{area_m2} m2", _contact())
        assert "None" not in msg


class TestDryRun:
    def test_empty(self):
        r = svc.dry_run(_campaign(), [])
        assert r.would_send == 0
        assert r.dry_run

    def test_contacts(self):
        contacts = [_contact(id=i) for i in range(5)]
        r = svc.dry_run(_campaign(), contacts, max_recipients=3)
        assert r.would_send == 3
        assert r.skipped == 2

    def test_blocked_counted(self):
        contacts = [_contact(id=1, lead_status="stopped"), _contact(id=2)]
        r = svc.dry_run(_campaign(), contacts)
        assert r.blocked == 1
        assert r.would_send == 1

    def test_sample_messages(self):
        r = svc.dry_run(_campaign(), [_contact()])
        assert len(r.sample_messages) == 1
        assert "Ali" in r.sample_messages[0]

    def test_canary_blocks(self):
        contacts = [_contact(id=1), _contact(id=2)]
        r = svc.dry_run(_campaign(), contacts, canary_enabled=True, canary_ids={1})
        assert r.blocked == 1
        assert r.would_send == 1


class TestBuildSendAttempt:
    def test_basic(self):
        a = svc.build_send_attempt(1, 2, telegram_user_id=123, status="proposed", batch_id="b1")
        assert a["campaign_id"] == 1
        assert a["contact_id"] == 2
        assert a["status"] == "proposed"
        assert a["batch_id"] == "b1"

    def test_message_preview_truncated(self):
        a = svc.build_send_attempt(1, 2, message_preview="x" * 500)
        assert len(a["message_preview"]) <= 200


class TestMarkAttempt:
    def test_sent(self):
        d = svc.mark_attempt_sent(telegram_message_id=999)
        assert d["status"] == "sent"
        assert d["telegram_message_id"] == 999

    def test_failed(self):
        d = svc.mark_attempt_failed("timeout error")
        assert d["status"] == "failed"
        assert "timeout" in d["error_message"]

    def test_failed_sanitized(self):
        d = svc.mark_attempt_failed("sk-secret123 error")
        assert "sk-" not in d["error_message"]

    def test_blocked(self):
        d = svc.mark_attempt_blocked("stopped")
        assert d["status"] == "blocked"


class TestBatchId:
    def test_unique(self):
        b1 = svc.build_batch_id()
        b2 = svc.build_batch_id()
        assert b1 != b2
        assert b1.startswith("batch_")


class TestSanitize:
    def test_removes_hash(self):
        d = svc.sanitize_send_result({"telegram_chat_id_hash": "abc", "ok": True})
        assert "telegram_chat_id_hash" not in d

    def test_redacts_token(self):
        d = svc.sanitize_send_result({"note": "sk-secret123"})
        assert "sk-" not in d["note"]


class TestRedactError:
    def test_clean(self):
        assert svc.redact_error("timeout") == "timeout"

    def test_token(self):
        assert "sk-" not in svc.redact_error("sk-secret123 error")

    def test_truncated(self):
        assert len(svc.redact_error("x" * 1000)) <= 500


class TestImmutability:
    def test_validation_frozen(self):
        import pytest

        from core.services.crm_campaign_send_service import SendValidation

        r = SendValidation()
        with pytest.raises(AttributeError):
            r.allowed = True  # type: ignore[misc]

    def test_dry_run_frozen(self):
        import pytest

        from core.services.crm_campaign_send_service import DryRunResult

        r = DryRunResult()
        with pytest.raises(AttributeError):
            r.would_send = 5  # type: ignore[misc]

    def test_send_result_frozen(self):
        import pytest

        from core.services.crm_campaign_send_service import SendResult

        r = SendResult()
        with pytest.raises(AttributeError):
            r.ok = True  # type: ignore[misc]
