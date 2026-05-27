"""Shared pytest fixtures for all test layers."""
from __future__ import annotations

import os

# Ensure tests run in development mode regardless of .env file values.
# Must be set before any import triggers get_settings().
os.environ.setdefault("APP_ENV", "development")

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


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


@pytest.fixture
def mock_admin_group_repo() -> AsyncMock:
    """Mock AbstractAdminGroupRepository for service tests."""
    from core.repositories.admin_group_repo import AbstractAdminGroupRepository
    return AsyncMock(spec=AbstractAdminGroupRepository)


@pytest.fixture
def mock_broadcast_repo() -> AsyncMock:
    """Mock AbstractBroadcastRepository for broadcast service tests."""
    from core.repositories.broadcast_repo import AbstractBroadcastRepository
    return AsyncMock(spec=AbstractBroadcastRepository)


@pytest.fixture
def mock_journey_session() -> AsyncMock:
    """Mock AsyncSession for JourneyEventService tests."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session
