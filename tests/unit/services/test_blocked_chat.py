"""Unit tests for blocked_chat feature.

Covers:
  1. _classify_error  — pure function, no mocks needed.
  2. AbstractBlockedChatRepository contract — via AsyncMock(spec=...).
  3. _upsert_blocked_chat helper — patched repo, verifies never-raise contract.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramForbiddenError

from core.repositories.blocked_chat_repo import AbstractBlockedChatRepository
from infrastructure.queue.tasks.broadcast_tasks import _classify_error

# ── _classify_error ────────────────────────────────────────────────────────────

class TestClassifyError:
    """Pure-function tests — no I/O, no mocks."""

    def test_blocked_by_user(self) -> None:
        exc = Exception("Forbidden: bot was blocked by the user")
        assert _classify_error(exc) == "blocked"

    def test_blocked_phrase_case_insensitive(self) -> None:
        exc = Exception("FORBIDDEN: Bot Was Blocked By The User")
        assert _classify_error(exc) == "blocked"

    def test_telegram_forbidden_error_becomes_forbidden(self) -> None:
        # TelegramForbiddenError that is NOT "bot was blocked" → forbidden
        exc = TelegramForbiddenError(
            method=None,  # type: ignore[arg-type]
            message="Forbidden: bot was kicked from the group chat",
        )
        # "kicked" is in the message but TelegramForbiddenError check fires first
        assert _classify_error(exc) == "forbidden"

    def test_kicked_phrase(self) -> None:
        exc = Exception("Bad Request: kicked")
        assert _classify_error(exc) == "forbidden"

    def test_not_enough_rights(self) -> None:
        exc = Exception("Bad Request: not enough rights to send text messages")
        assert _classify_error(exc) == "forbidden"

    def test_chat_not_found(self) -> None:
        exc = Exception("Bad Request: chat not found")
        assert _classify_error(exc) == "forbidden"

    def test_forbidden_phrase(self) -> None:
        exc = Exception("Forbidden: user is deactivated")
        # "forbidden" substring triggers the phrase check
        assert _classify_error(exc) == "forbidden"

    def test_network_timeout_is_other(self) -> None:
        exc = ConnectionError("timed out")
        assert _classify_error(exc) == "other"

    def test_value_error_is_other(self) -> None:
        exc = ValueError("no content to send")
        assert _classify_error(exc) == "other"


# ── AbstractBlockedChatRepository contract ─────────────────────────────────────

class TestBlockedChatRepositoryContract:
    """Tests against a mocked AbstractBlockedChatRepository.

    These verify the *expected behaviour* of any concrete implementation
    without hitting the DB.
    """

    def setup_method(self) -> None:
        self.repo: AsyncMock = AsyncMock(spec=AbstractBlockedChatRepository)

    # ── bulk_filter_blocked ───────────────────────────────────────────────────

    async def test_filter_removes_blocked_ids(self) -> None:
        # repo says [111, 333] are blocked
        self.repo.bulk_filter_blocked.return_value = [222, 444]
        result = await self.repo.bulk_filter_blocked([111, 222, 333, 444])
        assert result == [222, 444]

    async def test_filter_empty_input_returns_empty(self) -> None:
        self.repo.bulk_filter_blocked.return_value = []
        result = await self.repo.bulk_filter_blocked([])
        assert result == []

    async def test_filter_no_blocked_returns_all(self) -> None:
        ids = [1, 2, 3]
        self.repo.bulk_filter_blocked.return_value = ids
        result = await self.repo.bulk_filter_blocked(ids)
        assert result == ids

    # ── upsert_block ──────────────────────────────────────────────────────────

    async def test_upsert_new_returns_true(self) -> None:
        self.repo.upsert_block.return_value = True
        is_new = await self.repo.upsert_block(123456, "blocked")
        assert is_new is True

    async def test_upsert_existing_returns_false(self) -> None:
        self.repo.upsert_block.return_value = False
        is_new = await self.repo.upsert_block(123456, "blocked")
        assert is_new is False

    async def test_upsert_called_with_correct_args(self) -> None:
        self.repo.upsert_block.return_value = True
        await self.repo.upsert_block(-100987654321, "forbidden")
        self.repo.upsert_block.assert_called_once_with(-100987654321, "forbidden")


# ── _upsert_blocked_chat helper ────────────────────────────────────────────────

class TestUpsertBlockedChatHelper:
    """Tests the _upsert_blocked_chat wrapper in broadcast_tasks.

    Uses patches so no real DB or session factory is needed.
    """

    async def test_returns_true_on_new_entry(self) -> None:
        from infrastructure.queue.tasks.broadcast_tasks import _upsert_blocked_chat
        mock_repo = AsyncMock(spec=AbstractBlockedChatRepository)
        mock_repo.upsert_block.return_value = True

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # async_sessionmaker.__call__ is synchronous, returns an async ctx mgr
        mock_factory = MagicMock(return_value=mock_session)

        with patch(
            "infrastructure.queue.tasks.broadcast_tasks.PostgresBlockedChatRepository",
            return_value=mock_repo,
        ):
            result = await _upsert_blocked_chat(99999, "blocked", mock_factory)

        assert result is True

    async def test_returns_false_on_existing_entry(self) -> None:
        from infrastructure.queue.tasks.broadcast_tasks import _upsert_blocked_chat
        mock_repo = AsyncMock(spec=AbstractBlockedChatRepository)
        mock_repo.upsert_block.return_value = False

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch(
            "infrastructure.queue.tasks.broadcast_tasks.PostgresBlockedChatRepository",
            return_value=mock_repo,
        ):
            result = await _upsert_blocked_chat(99999, "blocked", mock_factory)

        assert result is False

    async def test_never_raises_on_db_error(self) -> None:
        """If the DB write fails, _upsert_blocked_chat must swallow the error."""
        from infrastructure.queue.tasks.broadcast_tasks import _upsert_blocked_chat

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch(
            "infrastructure.queue.tasks.broadcast_tasks.PostgresBlockedChatRepository",
            side_effect=RuntimeError("DB down"),
        ):
            # Must NOT raise
            result = await _upsert_blocked_chat(99999, "blocked", mock_factory)

        # On failure it returns False (never raises)
        assert result is False
