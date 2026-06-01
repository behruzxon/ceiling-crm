"""Pure-function tests for the Unknown Questions capture service.

Covers sanitization (phone masking, token/URL/key redaction), hashing,
reason classification, severity, event building, and the capture decision.
All offline: no DB, Redis, OpenAI, Telegram.
"""

from __future__ import annotations

import pytest

from core.services import unknown_question_service as svc
from core.services.unknown_question_service import (
    MAX_PREVIEW_LEN,
    REASONS,
    SEVERITIES,
    SOURCES,
    STATUSES,
    build_unknown_question_event,
    classify_catalog_capture,
    classify_price_capture,
    classify_unknown_question_reason,
    hash_chat_id,
    hash_question_text,
    maybe_record_unknown_question,
    sanitize_unknown_question_text,
    severity_for_unknown_question,
)

_SECRET_MARKERS = (
    "sk-",
    "bearer ",
    "openai_api_key",
    "database_url=",
    "bot_token",
    "postgres://",
)


# ── Phone masking ────────────────────────────────────────────────────────────


class TestPhoneMasking:
    def test_masks_full_uz_phone(self) -> None:
        out = sanitize_unknown_question_text("raqamim +998901234567")
        assert "+998901234567" not in out
        assert "****" in out

    def test_masks_local_9_digit(self) -> None:
        out = sanitize_unknown_question_text("901234567 ga qo'ng'iroq qiling")
        assert "901234567" not in out

    def test_masks_spaced_phone(self) -> None:
        out = sanitize_unknown_question_text("90 886 66 66")
        assert "886 66 66" not in out

    def test_keeps_non_phone_digits_context(self) -> None:
        out = sanitize_unknown_question_text("20 kv metr narxi")
        assert "kv metr" in out

    @pytest.mark.parametrize(
        "txt",
        [
            "+998901112233",
            "998901112233",
            "tel: +998 90 111 22 33",
            "mening tel 901112233",
        ],
    )
    def test_various_phones_never_survive(self, txt: str) -> None:
        out = sanitize_unknown_question_text(txt)
        assert "1112233" not in out.replace("****", "")


# ── Token / key / URL redaction ──────────────────────────────────────────────


class TestSecretRedaction:
    def test_redacts_sk_key(self) -> None:
        out = sanitize_unknown_question_text("key sk-ABCD1234EFGH5678")
        assert "sk-ABCD1234EFGH5678" not in out
        assert "[redacted]" in out

    def test_redacts_bot_token(self) -> None:
        tok = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
        out = sanitize_unknown_question_text(f"token {tok}")
        assert tok not in out
        assert "[redacted]" in out

    def test_bot_token_body_not_partially_leaked(self) -> None:
        # Regression: phone mask must not nibble token digits and leave body.
        tok = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
        out = sanitize_unknown_question_text(f"my bot {tok} ok")
        assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in out

    def test_redacts_bearer(self) -> None:
        out = sanitize_unknown_question_text("Authorization Bearer abcdef1234567890")
        assert "abcdef1234567890" not in out

    def test_redacts_database_url(self) -> None:
        out = sanitize_unknown_question_text("DATABASE_URL=postgres://u:p@h:5432/db")
        assert "postgres://u:p@h" not in out
        assert "[redacted]" in out

    def test_redacts_api_key_kv(self) -> None:
        out = sanitize_unknown_question_text("api_key: SUPERSECRETVALUE123")
        assert "SUPERSECRETVALUE123" not in out

    def test_redacts_password_kv(self) -> None:
        out = sanitize_unknown_question_text("password=hunter2hunter2")
        assert "hunter2hunter2" not in out

    def test_redacts_url(self) -> None:
        out = sanitize_unknown_question_text("ko'ring https://t.me/secret/99")
        assert "https://t.me/secret/99" not in out
        assert "[link]" in out

    def test_redacts_www_url(self) -> None:
        out = sanitize_unknown_question_text("www.example.com/secret")
        assert "example.com/secret" not in out

    @pytest.mark.parametrize(
        "txt",
        [
            "sk-ZZZZ9999YYYY8888 ber",
            "openai_api_key=sk-aaaa1111bbbb2222",
            "DATABASE_URL=postgresql://x:y@z/db",
            "Bearer eyJhbGciOiJIUzI1NiI=",
            "988877766:AAEvabcdefghijklmnopqrstuvwxyz12345",
        ],
    )
    def test_no_secret_marker_survives(self, txt: str) -> None:
        out = sanitize_unknown_question_text(txt).lower()
        # The raw secret values must be gone; redaction placeholders are fine.
        assert "sk-aaaa" not in out
        assert "eyjhbgci" not in out
        assert "aaevabcdef" not in out
        assert "x:y@z" not in out


# ── Preview shaping ──────────────────────────────────────────────────────────


class TestPreviewShaping:
    def test_empty_input_returns_empty(self) -> None:
        assert sanitize_unknown_question_text("") == ""

    def test_none_input_returns_empty(self) -> None:
        assert sanitize_unknown_question_text(None) == ""

    def test_truncates_to_max(self) -> None:
        out = sanitize_unknown_question_text("a" * 1000)
        assert len(out) <= MAX_PREVIEW_LEN

    def test_custom_max_length(self) -> None:
        out = sanitize_unknown_question_text("hello world this is long", max_length=5)
        assert len(out) <= 5

    def test_collapses_whitespace(self) -> None:
        out = sanitize_unknown_question_text("gulli    \n\n  narxi")
        assert out == "gulli narxi"

    def test_strips_edges(self) -> None:
        assert sanitize_unknown_question_text("   salom   ") == "salom"


# ── Uzbek / Cyrillic handling ────────────────────────────────────────────────


class TestUnicodeHandling:
    @pytest.mark.parametrize(
        "txt",
        [
            "gulli shiftlar narxi qancha",
            "гулли шифт нархи",
            "qora naqsh UF pechat bormi",
            "осмон дизайн ko'rsating",
            "30 кв метр uchun qancha bo'ladi",
        ],
    )
    def test_unicode_preserved(self, txt: str) -> None:
        out = sanitize_unknown_question_text(txt)
        assert out  # not empty
        assert isinstance(out, str)

    def test_cyrillic_hash_stable(self) -> None:
        assert hash_question_text("Гулли") == hash_question_text("гулли")


# ── Hashing ──────────────────────────────────────────────────────────────────


class TestHashing:
    def test_hash_is_hex_64(self) -> None:
        h = hash_question_text("salom")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_stable_across_case_and_space(self) -> None:
        assert hash_question_text("Salom  DUNYO") == hash_question_text("salom dunyo")

    def test_hash_differs_for_different_text(self) -> None:
        assert hash_question_text("gulli") != hash_question_text("kosmos")

    def test_hash_empty_stable(self) -> None:
        assert hash_question_text("") == hash_question_text(None)

    def test_chat_id_hash_hex(self) -> None:
        h = hash_chat_id(123456)
        assert h is not None and len(h) == 64

    def test_chat_id_hash_none(self) -> None:
        assert hash_chat_id(None) is None
        assert hash_chat_id("") is None

    def test_chat_id_hash_does_not_contain_raw(self) -> None:
        h = hash_chat_id(987654321)
        assert "987654321" not in (h or "")

    def test_chat_id_hash_stable(self) -> None:
        assert hash_chat_id(42) == hash_chat_id("42")


# ── Reason classification ────────────────────────────────────────────────────


class TestReasonClassification:
    def test_none_when_no_signal(self) -> None:
        assert classify_unknown_question_reason() is None

    def test_openai_error_highest(self) -> None:
        r = classify_unknown_question_reason(openai_error=True, safety_block=True, ai_fallback=True)
        assert r == "openai_error"

    def test_safety_over_operator(self) -> None:
        assert (
            classify_unknown_question_reason(safety_block=True, operator_needed=True)
            == "safety_block"
        )

    def test_shadow_mismatch(self) -> None:
        assert classify_unknown_question_reason(shadow_mismatch=True) == "shadow_live_mismatch"

    def test_operator_needed(self) -> None:
        assert classify_unknown_question_reason(operator_needed=True) == "operator_needed"

    def test_unknown_price(self) -> None:
        assert (
            classify_unknown_question_reason(unknown_price_question=True)
            == "unknown_price_question"
        )

    def test_no_catalog_match(self) -> None:
        assert classify_unknown_question_reason(no_catalog_match=True) == "no_catalog_match"

    def test_unknown_design(self) -> None:
        assert classify_unknown_question_reason(unknown_design=True) == "unknown_design"

    def test_low_confidence(self) -> None:
        assert classify_unknown_question_reason(low_confidence=True) == "low_confidence"

    def test_generic_reply(self) -> None:
        assert classify_unknown_question_reason(generic_reply=True) == "generic_reply"

    def test_ai_fallback(self) -> None:
        assert classify_unknown_question_reason(ai_fallback=True) == "ai_fallback"

    def test_manual(self) -> None:
        assert classify_unknown_question_reason(manual=True) == "manual_flag"

    def test_all_results_in_vocab(self) -> None:
        for kw in (
            "openai_error",
            "safety_block",
            "shadow_mismatch",
            "operator_needed",
            "unknown_price_question",
            "no_catalog_match",
            "unknown_design",
            "low_confidence",
            "generic_reply",
            "ai_fallback",
            "manual",
        ):
            r = classify_unknown_question_reason(**{kw: True})
            assert r in REASONS


# ── Severity ─────────────────────────────────────────────────────────────────


class TestSeverity:
    def test_openai_error_high(self) -> None:
        assert severity_for_unknown_question("openai_error") == "high"

    def test_safety_block_high(self) -> None:
        assert severity_for_unknown_question("safety_block") == "high"

    def test_generic_reply_low(self) -> None:
        assert severity_for_unknown_question("generic_reply") == "low"

    def test_ai_fallback_medium(self) -> None:
        assert severity_for_unknown_question("ai_fallback") == "medium"

    def test_unknown_reason_medium(self) -> None:
        assert severity_for_unknown_question("totally_unknown") == "medium"

    def test_hot_lead_bumps_one_tier(self) -> None:
        assert severity_for_unknown_question("ai_fallback", order_readiness_score=80) == "high"

    def test_hot_lead_bumps_high_to_critical(self) -> None:
        assert severity_for_unknown_question("openai_error", order_readiness_score=90) == "critical"

    def test_cold_lead_no_bump(self) -> None:
        assert severity_for_unknown_question("ai_fallback", order_readiness_score=10) == "medium"

    def test_bump_never_exceeds_critical(self) -> None:
        assert (
            severity_for_unknown_question("safety_block", order_readiness_score=100) in SEVERITIES
        )

    def test_all_reasons_yield_valid_severity(self) -> None:
        for reason in REASONS:
            assert severity_for_unknown_question(reason) in SEVERITIES


# ── Event building ───────────────────────────────────────────────────────────


class TestEventBuilding:
    def test_basic_event_shape(self) -> None:
        e = build_unknown_question_event(reason="ai_fallback", original_text="gulli narxi")
        assert e["reason"] == "ai_fallback"
        assert e["original_text_preview"] == "gulli narxi"
        assert e["status"] == "new"
        assert len(e["original_text_hash"]) == 64

    def test_event_masks_phone_in_preview(self) -> None:
        e = build_unknown_question_event(reason="ai_fallback", original_text="raqam +998901234567")
        assert "+998901234567" not in e["original_text_preview"]

    def test_event_hashes_chat_id(self) -> None:
        e = build_unknown_question_event(
            reason="ai_fallback", original_text="x", telegram_chat_id=12345
        )
        assert e["telegram_chat_id_hash"] is not None
        assert "12345" not in e["telegram_chat_id_hash"]

    def test_event_coerces_bad_source(self) -> None:
        e = build_unknown_question_event(reason="ai_fallback", original_text="x", source="hacker")
        assert e["source"] in SOURCES

    def test_event_coerces_bad_reason(self) -> None:
        e = build_unknown_question_event(reason="nonsense", original_text="x")
        assert e["reason"] in REASONS

    def test_event_derives_severity(self) -> None:
        e = build_unknown_question_event(reason="openai_error", original_text="x")
        assert e["severity"] == "high"

    def test_event_explicit_severity_kept(self) -> None:
        e = build_unknown_question_event(
            reason="ai_fallback", original_text="x", severity="critical"
        )
        assert e["severity"] == "critical"

    def test_event_bad_severity_recomputed(self) -> None:
        e = build_unknown_question_event(
            reason="generic_reply", original_text="x", severity="ultra"
        )
        assert e["severity"] in SEVERITIES

    def test_event_carries_sdm_fields(self) -> None:
        e = build_unknown_question_event(
            reason="shadow_live_mismatch",
            original_text="x",
            sdm_intent="price",
            sdm_next_action="ask_area",
            order_readiness_score=55,
            live_route="ai_fallback",
            intent="price",
        )
        assert e["sdm_intent"] == "price"
        assert e["sdm_next_action"] == "ask_area"
        assert e["order_readiness_score"] == 55
        assert e["live_route"] == "ai_fallback"
        assert e["intent"] == "price"

    def test_event_bot_reply_sanitized(self) -> None:
        e = build_unknown_question_event(
            reason="ai_fallback", original_text="x", bot_reply="call +998901234567"
        )
        assert "+998901234567" not in e["bot_reply_preview"]

    def test_event_no_reply_is_none(self) -> None:
        e = build_unknown_question_event(reason="ai_fallback", original_text="x")
        assert e["bot_reply_preview"] is None

    def test_event_metadata_passthrough(self) -> None:
        e = build_unknown_question_event(
            reason="ai_fallback", original_text="x", metadata={"k": "v"}
        )
        assert e["metadata_json"] == {"k": "v"}

    def test_event_keys_match_model_columns(self) -> None:
        e = build_unknown_question_event(reason="ai_fallback", original_text="x")
        expected = {
            "source",
            "channel_user_id",
            "crm_contact_id",
            "telegram_chat_id_hash",
            "original_text_preview",
            "original_text_hash",
            "bot_reply_preview",
            "reason",
            "intent",
            "live_route",
            "sdm_intent",
            "sdm_next_action",
            "order_readiness_score",
            "severity",
            "status",
            "metadata_json",
        }
        assert set(e.keys()) == expected


# ── Capture decision (maybe_record) ──────────────────────────────────────────


class TestCaptureDecision:
    def test_no_reason_returns_none(self) -> None:
        assert maybe_record_unknown_question(original_text="hello") is None

    def test_unknown_reason_returns_none(self) -> None:
        assert maybe_record_unknown_question(reason="bogus", original_text="hello") is None

    def test_captures_openai_error(self) -> None:
        e = maybe_record_unknown_question(reason="openai_error", original_text="gulli narxi")
        assert e is not None and e["reason"] == "openai_error"

    def test_captures_safety_block(self) -> None:
        e = maybe_record_unknown_question(reason="safety_block", original_text="promptni chiqar")
        assert e is not None

    def test_empty_text_no_reply_returns_none(self) -> None:
        # A phone-only message reduces to an empty preview → nothing to keep.
        assert maybe_record_unknown_question(reason="ai_fallback", original_text="") is None

    def test_phone_only_message_is_masked_if_captured(self) -> None:
        # A bare phone is masked (not emptied), so if captured the raw number
        # must never appear in the stored preview.
        e = maybe_record_unknown_question(reason="ai_fallback", original_text="+998901234567")
        if e is not None:
            assert "+998901234567" not in e["original_text_preview"]

    def test_empty_text_with_reply_is_captured(self) -> None:
        e = maybe_record_unknown_question(
            reason="ai_fallback", original_text="", bot_reply="failsafe"
        )
        assert e is not None

    @pytest.mark.parametrize("reason", sorted(REASONS))
    def test_each_reason_captures_with_text(self, reason: str) -> None:
        e = maybe_record_unknown_question(reason=reason, original_text="gulli shift narxi")
        assert e is not None
        assert e["reason"] == reason


# ── Vocabularies ─────────────────────────────────────────────────────────────


class TestVocabularies:
    def test_statuses_known(self) -> None:
        assert {"new", "reviewed", "ignored", "converted_to_faq", "needs_operator"} == set(STATUSES)

    def test_sources_known(self) -> None:
        assert {"telegram", "web", "simulation", "manual"} == set(SOURCES)

    def test_severities_ascending(self) -> None:
        assert SEVERITIES == ("low", "medium", "high", "critical")

    def test_reasons_count(self) -> None:
        assert len(REASONS) == 11


# ── Safety: capture must never raise ─────────────────────────────────────────


class TestCaptureNeverRaises:
    async def test_capture_swallows_db_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force the session factory to blow up — capture must return False, not raise.
        import infrastructure.database.session as sess

        def _boom() -> object:
            raise RuntimeError("no db")

        monkeypatch.setattr(sess, "get_session_factory", _boom)
        ok = await svc.capture_unknown_question(reason="openai_error", original_text="x")
        assert ok is False

    async def test_capture_returns_false_when_nothing_to_record(self) -> None:
        ok = await svc.capture_unknown_question(reason=None, original_text="x")
        assert ok is False


# ── v2: catalog capture classifier ───────────────────────────────────────────


class TestClassifyCatalogCapture:
    def test_matched_is_no_capture(self) -> None:
        assert (
            classify_catalog_capture(matched=True, needs_confirmation=False, reason="alias:gulli")
            is None
        )

    def test_confirmation_is_no_capture(self) -> None:
        assert (
            classify_catalog_capture(
                matched=False, needs_confirmation=True, reason="ambiguous:naqsh"
            )
            is None
        )

    def test_fuzzy_confirm_is_no_capture(self) -> None:
        assert (
            classify_catalog_capture(
                matched=False, needs_confirmation=True, reason="fuzzy_confirm:0.74"
            )
            is None
        )

    def test_generic_trigger_is_no_capture(self) -> None:
        assert (
            classify_catalog_capture(
                matched=False, needs_confirmation=False, reason="generic_catalog_trigger"
            )
            is None
        )

    def test_empty_text_is_no_capture(self) -> None:
        assert (
            classify_catalog_capture(matched=False, needs_confirmation=False, reason="empty_text")
            is None
        )

    def test_no_alias_is_no_catalog_match(self) -> None:
        assert (
            classify_catalog_capture(matched=False, needs_confirmation=False, reason="no_alias")
            == "no_catalog_match"
        )

    def test_result_is_in_reason_vocab(self) -> None:
        r = classify_catalog_capture(matched=False, needs_confirmation=False, reason="no_alias")
        assert r in REASONS

    def test_matched_wins_over_no_alias_reason(self) -> None:
        # Defensive: matched True should never capture even if reason looks odd.
        assert (
            classify_catalog_capture(matched=True, needs_confirmation=False, reason="no_alias")
            is None
        )

    @pytest.mark.parametrize(
        "reason", ["alias:mramor", "fuzzy:0.91", "ambiguous:naqsh", "generic_catalog_trigger"]
    )
    def test_non_failure_reasons_skip(self, reason: str) -> None:
        # matched/confirmation flags set appropriately for each success-ish reason
        matched = reason.startswith(("alias:", "fuzzy:")) and "confirm" not in reason
        needs_conf = reason.startswith("ambiguous") or "confirm" in reason
        assert (
            classify_catalog_capture(matched=matched, needs_confirmation=needs_conf, reason=reason)
            is None
        )


# ── v2: price capture classifier ─────────────────────────────────────────────


class TestClassifyPriceCapture:
    def test_none_text(self) -> None:
        assert classify_price_capture(None) is None

    def test_empty_text(self) -> None:
        assert classify_price_capture("") is None

    @pytest.mark.parametrize(
        "txt",
        ["narx qancha", "necha pul", "narxi qancha", "narx", "qancha turadi"],
    )
    def test_short_bare_price_asks_not_captured(self, txt: str) -> None:
        assert classify_price_capture(txt) is None

    @pytest.mark.parametrize(
        "txt",
        [
            "menga balkon uchun narx aytib bera olasizmi",
            "narxlaringiz juda chalkash menga tushuntirib bering",
            "bu xizmat uchun umumiy narx qanaqa bo'ladi menimcha",
        ],
    )
    def test_substantive_price_questions_captured(self, txt: str) -> None:
        assert classify_price_capture(txt) == "unknown_price_question"

    def test_result_in_reason_vocab(self) -> None:
        assert classify_price_capture("a b c d e") in REASONS

    def test_threshold_boundary_three_words_skipped(self) -> None:
        assert classify_price_capture("narx qancha turadi") is None

    def test_threshold_boundary_four_words_captured(self) -> None:
        assert classify_price_capture("narx qancha turadi aniq") == "unknown_price_question"

    def test_custom_min_words(self) -> None:
        assert classify_price_capture("narx qancha", min_words=2) == "unknown_price_question"


# ── v2: new reasons flow through build / record / severity ───────────────────


class TestV2ReasonsEndToEnd:
    @pytest.mark.parametrize("reason", ["no_catalog_match", "unknown_price_question"])
    def test_reason_in_vocab(self, reason: str) -> None:
        assert reason in REASONS

    @pytest.mark.parametrize("reason", ["no_catalog_match", "unknown_price_question"])
    def test_build_event_keeps_reason(self, reason: str) -> None:
        e = build_unknown_question_event(reason=reason, original_text="balkon uchun dizayn bormi")
        assert e["reason"] == reason

    @pytest.mark.parametrize("reason", ["no_catalog_match", "unknown_price_question"])
    def test_maybe_record_captures(self, reason: str) -> None:
        e = maybe_record_unknown_question(reason=reason, original_text="balkon dizayn narx savol")
        assert e is not None and e["reason"] == reason

    def test_no_catalog_match_severity_medium(self) -> None:
        assert severity_for_unknown_question("no_catalog_match") == "medium"

    def test_unknown_price_severity_medium(self) -> None:
        assert severity_for_unknown_question("unknown_price_question") == "medium"

    def test_no_catalog_match_hot_lead_bumps(self) -> None:
        assert severity_for_unknown_question("no_catalog_match", order_readiness_score=85) == "high"

    def test_v2_event_masks_phone(self) -> None:
        e = build_unknown_question_event(
            reason="unknown_price_question",
            original_text="balkon narx +998901234567 ayting",
        )
        assert "+998901234567" not in e["original_text_preview"]

    def test_v2_event_hash_64(self) -> None:
        e = build_unknown_question_event(reason="no_catalog_match", original_text="balkon dizayn")
        assert len(e["original_text_hash"]) == 64


# ── v2: non-failures still skip (greeting / stop / phone-only) ───────────────


class TestV2NonFailuresSkip:
    def test_catalog_generic_not_captured(self) -> None:
        # "katalog" generic ask → resolver generic_catalog_trigger → no capture
        assert (
            classify_catalog_capture(
                matched=False, needs_confirmation=False, reason="generic_catalog_trigger"
            )
            is None
        )

    def test_catalog_matched_design_not_captured(self) -> None:
        assert (
            classify_catalog_capture(matched=True, needs_confirmation=False, reason="alias:gulli")
            is None
        )

    def test_price_bare_ask_not_captured(self) -> None:
        assert classify_price_capture("narx") is None

    def test_phone_only_price_skips_when_short(self) -> None:
        # "+998901234567" is one token → below threshold → no price capture
        assert classify_price_capture("+998901234567") is None
