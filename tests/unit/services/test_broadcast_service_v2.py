"""Unit tests for BroadcastService v2 methods.

Tests focus on the service layer only — repo is mocked via AsyncMock.
Counter delegation, status changes, and reach estimation are covered.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from core.repositories.broadcast_repo import AbstractBroadcastRepository
from core.services.broadcast_service import BroadcastService
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType


class TestBroadcastServiceV2:

    def setup_method(self) -> None:
        self.repo: AsyncMock = AsyncMock(spec=AbstractBroadcastRepository)
        self.svc = BroadcastService(self.repo)

    # ── create_broadcast_v2 ───────────────────────────────────────────────

    async def test_create_returns_broadcast_id(self) -> None:
        self.repo.create_broadcast.return_value = 42
        bid = await self.svc.create_broadcast_v2(
            segment_type=SegmentType.ALL_PRIVATE,
            payload_type=PayloadType.TEXT,
            text="Hello everyone",
            file_id=None,
            created_by=1,
        )
        assert bid == 42

    async def test_create_passes_all_args(self) -> None:
        self.repo.create_broadcast.return_value = 7
        await self.svc.create_broadcast_v2(
            segment_type=SegmentType.LEAD_STAGE,
            payload_type=PayloadType.PHOTO,
            text="Caption",
            file_id="AgACAgI_xyz",
            created_by=99,
            lead_stage="CONTACTED",
        )
        self.repo.create_broadcast.assert_called_once_with(
            segment_type=SegmentType.LEAD_STAGE,
            payload_type=PayloadType.PHOTO,
            text="Caption",
            file_id="AgACAgI_xyz",
            created_by=99,
            lead_stage="CONTACTED",
        )

    # ── mark_status ───────────────────────────────────────────────────────

    async def test_mark_status_delegates(self) -> None:
        await self.svc.mark_status(1, BroadcastStatus.RUNNING)
        self.repo.mark_status.assert_called_once_with(1, BroadcastStatus.RUNNING)

    async def test_mark_done_delegates(self) -> None:
        await self.svc.mark_status(5, BroadcastStatus.DONE)
        self.repo.mark_status.assert_called_once_with(5, BroadcastStatus.DONE)

    # ── inc_sent / inc_failed ─────────────────────────────────────────────

    async def test_inc_sent_default_delta(self) -> None:
        await self.svc.inc_sent(10)
        self.repo.inc_sent.assert_called_once_with(10, 1)

    async def test_inc_sent_custom_delta(self) -> None:
        await self.svc.inc_sent(10, n=25)
        self.repo.inc_sent.assert_called_once_with(10, 25)

    async def test_inc_failed_default_delta(self) -> None:
        await self.svc.inc_failed(10)
        self.repo.inc_failed.assert_called_once_with(10, 1)

    async def test_inc_failed_custom_delta(self) -> None:
        await self.svc.inc_failed(10, n=3)
        self.repo.inc_failed.assert_called_once_with(10, 3)

    # ── finalize ──────────────────────────────────────────────────────────

    async def test_finalize_delegates_timestamp(self) -> None:
        ts = datetime(2026, 2, 27, 12, 0, 0, tzinfo=UTC)
        await self.svc.finalize(broadcast_id=3, finished_at=ts)
        self.repo.finalize.assert_called_once_with(3, ts)

    # ── estimate_reach_v2 ─────────────────────────────────────────────────

    async def test_estimate_all_private_uses_all_user_ids(self) -> None:
        self.repo.get_all_private_user_ids.return_value = [1, 2, 3, 4, 5]
        count = await self.svc.estimate_reach_v2(SegmentType.ALL_PRIVATE)
        assert count == 5
        self.repo.get_all_private_user_ids.assert_called_once()

    async def test_estimate_lead_stage_uses_stage_query(self) -> None:
        self.repo.get_user_ids_by_stage.return_value = [10, 20]
        count = await self.svc.estimate_reach_v2(SegmentType.LEAD_STAGE, lead_stage="NEW")
        assert count == 2
        self.repo.get_user_ids_by_stage.assert_called_once_with("NEW")

    async def test_estimate_lead_stage_without_stage_falls_back_to_all(self) -> None:
        """If LEAD_STAGE selected but lead_stage is None, fall back to all users."""
        self.repo.get_all_private_user_ids.return_value = [1, 2]
        count = await self.svc.estimate_reach_v2(SegmentType.LEAD_STAGE, lead_stage=None)
        assert count == 2
        self.repo.get_all_private_user_ids.assert_called_once()

    async def test_estimate_admin_groups_falls_back_to_all_users(self) -> None:
        """ADMIN_GROUPS segment: estimate_reach_v2 returns private user count (group count
        is not tracked in broadcast_repo — only the worker resolves group_ids)."""
        self.repo.get_all_private_user_ids.return_value = [1]
        count = await self.svc.estimate_reach_v2(SegmentType.ADMIN_GROUPS)
        assert count == 1

    # ── get_broadcast ─────────────────────────────────────────────────────

    async def test_get_broadcast_returns_none_when_missing(self) -> None:
        self.repo.get_by_id.return_value = None
        result = await self.svc.get_broadcast(999)
        assert result is None

    async def test_get_broadcast_delegates_to_repo(self) -> None:
        self.repo.get_by_id.return_value = None
        await self.svc.get_broadcast(5)
        self.repo.get_by_id.assert_called_once_with(5)
