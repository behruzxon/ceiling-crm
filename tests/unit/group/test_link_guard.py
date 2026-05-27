"""
Unit tests for link detection logic (C3-3) — link_guard.has_link().
Uses lightweight MagicMock objects to avoid aiogram type instantiation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from aiogram.enums import MessageEntityType

from apps.bot.handlers.group.link_guard import has_link


def _msg(
    text: str | None = None,
    caption: str | None = None,
    entities: list | None = None,
    caption_entities: list | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.caption = caption
    msg.entities = entities or []
    msg.caption_entities = caption_entities or []
    return msg


def _entity(entity_type: str) -> MagicMock:
    e = MagicMock()
    e.type = entity_type
    return e


# ─────────────────────────────────────────────────────────────────────────────
# Messages that must NOT be blocked
# ─────────────────────────────────────────────────────────────────────────────


class TestHasLinkNegative:
    def test_plain_text(self) -> None:
        assert has_link(_msg(text="Salom, qanday yordam bera olaman?")) is False

    def test_empty_message(self) -> None:
        assert has_link(_msg()) is False

    def test_user_mention_entity_not_blocked(self) -> None:
        """Regular @username Telegram MENTION entities must pass through."""
        assert (
            has_link(
                _msg(
                    text="@ali bu yerda",
                    entities=[_entity(MessageEntityType.MENTION)],
                )
            )
            is False
        )

    def test_short_text_no_link(self) -> None:
        assert has_link(_msg(text="Narx qancha?")) is False

    def test_number_only(self) -> None:
        assert has_link(_msg(text="12345678")) is False


# ─────────────────────────────────────────────────────────────────────────────
# Messages that MUST be blocked
# ─────────────────────────────────────────────────────────────────────────────


class TestHasLinkPositive:
    def test_url_entity_in_text(self) -> None:
        assert (
            has_link(
                _msg(
                    text="Check http://spam.com",
                    entities=[_entity(MessageEntityType.URL)],
                )
            )
            is True
        )

    def test_text_link_entity(self) -> None:
        assert (
            has_link(
                _msg(
                    text="Click here",
                    entities=[_entity(MessageEntityType.TEXT_LINK)],
                )
            )
            is True
        )

    def test_https_bare_in_text(self) -> None:
        assert has_link(_msg(text="visit https://example.com for details")) is True

    def test_http_bare_in_text(self) -> None:
        assert has_link(_msg(text="http://malicious.site")) is True

    def test_www_bare_in_text(self) -> None:
        assert has_link(_msg(text="go to www.spam.uz")) is True

    def test_t_me_link(self) -> None:
        assert has_link(_msg(text="join t.me/spamchannel now")) is True

    def test_url_entity_in_caption(self) -> None:
        assert (
            has_link(
                _msg(
                    caption="spam",
                    caption_entities=[_entity(MessageEntityType.URL)],
                )
            )
            is True
        )

    def test_https_in_caption(self) -> None:
        assert has_link(_msg(caption="https://spam.com")) is True

    def test_t_me_in_caption(self) -> None:
        assert has_link(_msg(caption="join t.me/ads")) is True

    def test_mixed_entities_url_wins(self) -> None:
        """If URL entity is present alongside MENTION, still blocked."""
        assert (
            has_link(
                _msg(
                    text="@user check https://spam.com",
                    entities=[
                        _entity(MessageEntityType.MENTION),
                        _entity(MessageEntityType.URL),
                    ],
                )
            )
            is True
        )
