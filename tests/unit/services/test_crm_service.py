"""Unit tests for CRMService pipeline transitions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.services.crm_service import CRMService
from shared.constants.enums import PipelineStage
from shared.exceptions.base import InvalidStageTransitionError


class TestCRMServiceTransitions:

    def setup_method(self):
        self.lead_repo = AsyncMock()
        self.pipeline_repo = AsyncMock()
        self.event_bus = AsyncMock()
        self.svc = CRMService(self.lead_repo, self.pipeline_repo, self.event_bus)

    def test_get_valid_transitions_new(self):
        transitions = self.svc.get_valid_transitions(PipelineStage.NEW)
        assert PipelineStage.CONTACTED in transitions
        assert PipelineStage.LOST in transitions

    def test_get_valid_transitions_completed_allows_undo(self):
        # COMPLETED can go back to INSTALLATION (undo / correction)
        transitions = self.svc.get_valid_transitions(PipelineStage.COMPLETED)
        assert PipelineStage.INSTALLATION in transitions
        # COMPLETED cannot jump forward to arbitrary stages
        assert PipelineStage.NEW not in transitions
        assert PipelineStage.LOST not in transitions

    def test_lost_re_engage_to_new(self):
        transitions = self.svc.get_valid_transitions(PipelineStage.LOST)
        assert PipelineStage.NEW in transitions

    @pytest.mark.asyncio
    async def test_advance_stage_invalid_transition_raises(self):
        # Mocked pipeline_repo returns a MagicMock (not a PipelineStage),
        # which falls through ALLOWED_TRANSITIONS lookup to [] → InvalidStageTransitionError
        with pytest.raises(InvalidStageTransitionError):
            await self.svc.advance_stage(1, PipelineStage.CONTACTED, actor_id=99)
