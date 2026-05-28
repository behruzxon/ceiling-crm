"""Tests for Step 9.1 — Phone log/notification masking sweep.

Closes blocker §1.3 of docs/AI_AGENT_SYSTEM/134.
"""

from __future__ import annotations

from decimal import Decimal

from core.domain.lead import Lead
from shared.constants.enums import CeilingCategory, LeadSource
from shared.utils.phone import (
    MASK_FILL,
    MASK_PREFIX_DIGITS,
    MASK_SUFFIX_DIGITS,
    extract_phone_from_text,
    is_valid_uz_phone,
    mask_phone,
    mask_phone_in_text,
    normalize_phone,
)

UZ_PHONE = "+998901234567"
UZ_PHONE_9DIGIT = "901234567"


# ── 1. Module API ──────────────────────────────────────────────────────


class TestModuleAPI:
    def test_mask_phone_callable(self):
        assert callable(mask_phone)

    def test_mask_phone_in_text_callable(self):
        assert callable(mask_phone_in_text)

    def test_mask_prefix_constant(self):
        assert MASK_PREFIX_DIGITS == 4

    def test_mask_suffix_constant(self):
        assert MASK_SUFFIX_DIGITS == 2

    def test_mask_fill_constant(self):
        assert MASK_FILL == "****"


# ── 2. mask_phone scalar behavior ─────────────────────────────────────


class TestMaskPhoneScalar:
    def test_mask_uz_998_format(self):
        assert mask_phone(UZ_PHONE) == "+998****67"

    def test_mask_preserves_leading_plus(self):
        assert mask_phone(UZ_PHONE).startswith("+998")

    def test_mask_preserves_last_two(self):
        assert mask_phone(UZ_PHONE).endswith("67")

    def test_mask_9digit_local(self):
        out = mask_phone(UZ_PHONE_9DIGIT)
        assert out.startswith("9012")
        assert out.endswith("67")
        assert MASK_FILL in out

    def test_mask_none_returns_empty(self):
        assert mask_phone(None) == ""

    def test_mask_empty_string(self):
        assert mask_phone("") == ""

    def test_mask_whitespace_only(self):
        assert mask_phone("   ") == ""

    def test_mask_short_input_returned_as_is(self):
        assert mask_phone("12345") == "12345"

    def test_mask_returns_str(self):
        assert isinstance(mask_phone(UZ_PHONE), str)

    def test_mask_hides_middle_digits(self):
        masked = mask_phone(UZ_PHONE)
        # Middle digits "9012345" should be gone (only the prefix +998 and last 2 67 remain)
        assert "9012345" not in masked

    def test_mask_idempotent(self):
        once = mask_phone(UZ_PHONE)
        twice = mask_phone(once)
        # Either short-circuit (input too short post-mask) or stays masked.
        assert MASK_FILL in twice or twice == once

    def test_no_raw_phone_in_mask_output(self):
        assert UZ_PHONE not in mask_phone(UZ_PHONE)


# ── 3. mask_phone_in_text behavior ─────────────────────────────────────


class TestMaskPhoneInText:
    def test_mask_in_text_replaces_uz(self):
        out = mask_phone_in_text(f"User said: {UZ_PHONE}")
        assert UZ_PHONE not in out
        assert "****" in out

    def test_mask_in_text_empty_string(self):
        assert mask_phone_in_text("") == ""

    def test_mask_in_text_none(self):
        assert mask_phone_in_text(None) == ""

    def test_mask_in_text_no_phone(self):
        assert mask_phone_in_text("hello world") == "hello world"

    def test_mask_in_text_multiple_phones(self):
        text = f"{UZ_PHONE} and {UZ_PHONE}"
        out = mask_phone_in_text(text)
        assert UZ_PHONE not in out
        assert out.count("****") >= 2

    def test_mask_in_text_spaced_digits(self):
        out = mask_phone_in_text("call 90 886 66 66 please")
        assert "90 886 66 66" not in out

    def test_mask_in_text_dashed_digits(self):
        out = mask_phone_in_text("call 90-886-66-66 please")
        assert "90-886-66-66" not in out

    def test_mask_in_text_keeps_surrounding_words(self):
        out = mask_phone_in_text(f"prefix {UZ_PHONE} suffix")
        assert "prefix" in out and "suffix" in out


# ── 4. Existing helpers remain intact (no regressions) ────────────────


class TestExistingHelpersStable:
    def test_normalize_phone_still_works(self):
        assert normalize_phone(UZ_PHONE_9DIGIT) == UZ_PHONE

    def test_is_valid_uz_phone_still_works(self):
        assert is_valid_uz_phone(UZ_PHONE) is True

    def test_extract_phone_from_text_still_works(self):
        assert extract_phone_from_text(f"tel {UZ_PHONE}") == UZ_PHONE


# ── 5. Notification text masks phones ──────────────────────────────────


def _fake_lead(phone: str = UZ_PHONE) -> Lead:
    return Lead(
        id=42,
        user_id=1,
        name="Salim",
        phone=phone,
        district="Yashnabad",
        room_area=Decimal("24"),
        category=CeilingCategory.GULLI,
        source=LeadSource.GROUP,
    )


class TestLeadNotificationPreviews:
    def test_new_lead_text_masks_phone(self):
        from core.services.lead_notification_service import LeadNotificationService

        text = LeadNotificationService._new_lead_text(_fake_lead())
        assert UZ_PHONE not in text
        assert "****" in text

    def test_hot_lead_text_masks_phone(self):
        from core.services.lead_notification_service import LeadNotificationService

        text = LeadNotificationService._hot_lead_text(_fake_lead())
        assert UZ_PHONE not in text
        assert "****" in text

    def test_new_lead_text_keeps_lead_id(self):
        from core.services.lead_notification_service import LeadNotificationService

        text = LeadNotificationService._new_lead_text(_fake_lead())
        assert "#42" in text or "/lead_42" in text

    def test_hot_lead_text_keeps_lead_id(self):
        from core.services.lead_notification_service import LeadNotificationService

        text = LeadNotificationService._hot_lead_text(_fake_lead())
        assert "#42" in text or "/lead_42" in text


# ── 6. Source-level grep: no raw `{phone}` in notification format strings ─


class TestSourceLevelGuards:
    def test_lead_notification_imports_mask_phone(self):
        src = open("core/services/lead_notification_service.py", encoding="utf-8").read()
        assert "from shared.utils.phone import mask_phone" in src

    def test_lead_notification_has_no_raw_phone_in_f_strings(self):
        src = open("core/services/lead_notification_service.py", encoding="utf-8").read()
        # The four f-strings that previously embedded raw phone should now use mask_phone.
        for pattern in (
            'f"📱 {lead.phone}',
            'f"📱 Telefon: {lead.phone}',
            'f"📱 {phone}\\n"',
            'f"Tel: {phone}"',
        ):
            assert pattern not in src, f"raw phone f-string still present: {pattern!r}"

    def test_ai_notifications_imports_mask_phone(self):
        src = open("apps/bot/handlers/private/ai_notifications.py", encoding="utf-8").read()
        assert "from shared.utils.phone import mask_phone" in src

    def test_ai_notifications_log_calls_use_mask(self):
        src = open("apps/bot/handlers/private/ai_notifications.py", encoding="utf-8").read()
        assert 'phone_capture_notify_failed", phone=mask_phone(phone)' in src
        assert 'notify_ai_lead_collected_failed", phone=mask_phone(phone)' in src

    def test_ai_notifications_log_calls_have_no_raw_phone(self):
        src = open("apps/bot/handlers/private/ai_notifications.py", encoding="utf-8").read()
        assert 'phone_capture_notify_failed", phone=phone)' not in src
        assert 'notify_ai_lead_collected_failed", phone=phone)' not in src


# ── 7. AI memory display already masks phone (regression guard) ───────


class TestAIMemoryDisplay:
    def test_agent_memory_masks_phone_field(self):
        src = open("core/services/agent_memory_service.py", encoding="utf-8").read()
        assert "phone_masked" in src

    def test_no_full_phone_in_agent_memory_render(self):
        # Sanity: the memory service must not write `mem.phone =` with raw phone.
        src = open("core/services/agent_memory_service.py", encoding="utf-8").read()
        # raw phone copy would look like "mem.phone = phone" – guard against it.
        assert "mem.phone = phone" not in src


# ── 8. CRM handoff preview keeps mask (regression guard) ──────────────


class TestHandoffMask:
    def test_crm_handoff_mask_phone_helper_present(self):
        from core.services.crm_operator_handoff_service import mask_phone as legacy

        assert legacy(UZ_PHONE) != UZ_PHONE

    def test_handoff_mask_short_input_returned_as_is(self):
        from core.services.crm_operator_handoff_service import mask_phone as legacy

        assert legacy("12345") == "12345"


# ── 9. Conversation replay mask helper ────────────────────────────────


class TestReplayMask:
    def test_replay_mask_in_text_replaces_phone(self):
        from core.services.crm_conversation_replay_service import mask_phone_in_text as legacy

        out = legacy(f"customer: {UZ_PHONE}")
        assert UZ_PHONE not in out


# ── 10. Notification call-site: draft lead text uses mask ─────────────


class TestDraftLeadNotification:
    def test_draft_lead_format_string_uses_mask(self):
        """The draft-lead admin-group text composes phone via mask_phone(...)."""
        src = open("core/services/lead_notification_service.py", encoding="utf-8").read()
        # The draft-lead body must include mask_phone(phone) in the f-string
        # rather than the bare {phone} placeholder.
        assert 'f"📱 {mask_phone(phone)}' in src
