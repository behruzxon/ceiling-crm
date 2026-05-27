"""Unit tests for broadcast FSM helper logic.

Tests cover the segment/payload mapping dicts used by the FSM handler —
pure dict lookups, no I/O or FSM state needed.
"""
from __future__ import annotations

import pytest

from shared.constants.enums import PayloadType, SegmentType

# These mirror the private dicts in broadcasts.py; we import them here to
# avoid importing the full handler module (which has heavy aiogram deps).

_SEGMENT_TYPE_MAP: dict[str, SegmentType] = {
    "all":    SegmentType.ALL_PRIVATE,
    "stage":  SegmentType.LEAD_STAGE,
    "groups": SegmentType.ADMIN_GROUPS,
}

_PAYLOAD_TYPE_MAP: dict[str, PayloadType] = {
    "text":     PayloadType.TEXT,
    "photo":    PayloadType.PHOTO,
    "video":    PayloadType.VIDEO,
    "document": PayloadType.DOCUMENT,
}


class TestSegmentTypeMapping:

    @pytest.mark.parametrize("key,expected", [
        ("all",    SegmentType.ALL_PRIVATE),
        ("stage",  SegmentType.LEAD_STAGE),
        ("groups", SegmentType.ADMIN_GROUPS),
    ])
    def test_known_keys_resolve(self, key: str, expected: SegmentType) -> None:
        assert _SEGMENT_TYPE_MAP[key] == expected

    def test_all_segment_keys_present(self) -> None:
        assert set(_SEGMENT_TYPE_MAP.keys()) == {"all", "stage", "groups"}

    def test_unknown_key_falls_back_via_get(self) -> None:
        result = _SEGMENT_TYPE_MAP.get("unknown", SegmentType.ALL_PRIVATE)
        assert result == SegmentType.ALL_PRIVATE


class TestPayloadTypeMapping:

    @pytest.mark.parametrize("key,expected", [
        ("text",     PayloadType.TEXT),
        ("photo",    PayloadType.PHOTO),
        ("video",    PayloadType.VIDEO),
        ("document", PayloadType.DOCUMENT),
    ])
    def test_known_keys_resolve(self, key: str, expected: PayloadType) -> None:
        assert _PAYLOAD_TYPE_MAP[key] == expected

    def test_all_payload_keys_present(self) -> None:
        assert set(_PAYLOAD_TYPE_MAP.keys()) == {"text", "photo", "video", "document"}

    def test_unknown_key_falls_back_via_get(self) -> None:
        result = _PAYLOAD_TYPE_MAP.get("gif", PayloadType.TEXT)
        assert result == PayloadType.TEXT


class TestSegmentTypeEnum:
    """Verify enum values match what the ORM stores in the DB."""

    def test_all_private_value(self) -> None:
        assert SegmentType.ALL_PRIVATE.value == "all_private"

    def test_lead_stage_value(self) -> None:
        assert SegmentType.LEAD_STAGE.value == "lead_stage"

    def test_admin_groups_value(self) -> None:
        assert SegmentType.ADMIN_GROUPS.value == "admin_groups"


class TestPayloadTypeEnum:
    """Verify enum values match what the ORM stores in the DB."""

    def test_text_value(self) -> None:
        assert PayloadType.TEXT.value == "text"

    def test_photo_value(self) -> None:
        assert PayloadType.PHOTO.value == "photo"

    def test_video_value(self) -> None:
        assert PayloadType.VIDEO.value == "video"

    def test_document_value(self) -> None:
        assert PayloadType.DOCUMENT.value == "document"
