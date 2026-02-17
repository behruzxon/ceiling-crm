"""Shared pytest fixtures for all test layers."""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Mock AbstractUserRepository for service tests."""
    return AsyncMock()


@pytest.fixture
def mock_lead_repo() -> AsyncMock:
    """Mock AbstractLeadRepository for service tests."""
    return AsyncMock()


@pytest.fixture
def mock_pipeline_repo() -> AsyncMock:
    """Mock AbstractPipelineRepository for service tests."""
    return AsyncMock()


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Mock EventBus that tracks emitted events."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus
