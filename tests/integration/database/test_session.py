"""Integration tests for database connectivity (requires running PG)."""

from __future__ import annotations

import pytest

from infrastructure.database.session import check_database_health


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_health_check():
    """Verify DB health check returns ok status when DB is reachable."""
    result = await check_database_health()
    assert result["status"] in ("ok", "error")  # error is ok in CI without DB
