"""Unit tests for AdminGroupService + AbstractAdminGroupRepository contract.

Service is tested by mocking the repo (AsyncMock).
Repo upsert/list logic is exercised via the service boundary.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.repositories.admin_group_repo import AbstractAdminGroupRepository
from core.services.admin_group_service import AdminGroupService


class TestAdminGroupService:

    def setup_method(self) -> None:
        self.repo: AsyncMock = AsyncMock(spec=AbstractAdminGroupRepository)
        self.svc = AdminGroupService(self.repo)

    # ── upsert_admin_group ────────────────────────────────────────────────

    async def test_upsert_delegates_to_repo(self) -> None:
        await self.svc.upsert_admin_group(chat_id=-100123, title="Test Group")
        self.repo.upsert.assert_called_once_with(-100123, "Test Group")

    async def test_upsert_propagates_repo_exception(self) -> None:
        self.repo.upsert.side_effect = RuntimeError("DB error")
        with pytest.raises(RuntimeError, match="DB error"):
            await self.svc.upsert_admin_group(chat_id=-100123, title="Fail")

    # ── list_all_chat_ids ─────────────────────────────────────────────────

    async def test_list_returns_repo_result(self) -> None:
        self.repo.list_all_chat_ids.return_value = [-100111, -100222, -100333]
        result = await self.svc.list_all_chat_ids()
        assert result == [-100111, -100222, -100333]

    async def test_list_empty_when_no_groups(self) -> None:
        self.repo.list_all_chat_ids.return_value = []
        result = await self.svc.list_all_chat_ids()
        assert result == []

    async def test_list_delegates_to_repo(self) -> None:
        self.repo.list_all_chat_ids.return_value = []
        await self.svc.list_all_chat_ids()
        self.repo.list_all_chat_ids.assert_called_once()
