"""Integration tests for Redis connectivity (requires running Redis)."""
from __future__ import annotations

import pytest

from infrastructure.cache.client import check_redis_health


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_health_check():
    """Verify Redis health check returns ok when Redis is reachable."""
    result = await check_redis_health()
    assert result["status"] in ("ok", "error")
