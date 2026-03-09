"""Tests for Redis-backed BotRegistry.

Verifies:
  1. Redis state persistence on status changes
  2. Ownership locks prevent duplicate bot execution
  3. Restart recovery re-creates bots from Redis state
  4. Multi-instance coordination (only one instance per bot)
  5. Heartbeat and ownership renewal
  6. Graceful degradation when Redis is unavailable
  7. Shutdown releases ownership and syncs state
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.bot_registry import (
    BotRegistry,
    BotRuntimeState,
    BotStatus,
    TenantBotConfig,
    _hash_token,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_db_tenant(**overrides) -> MagicMock:
    """Create a mock TenantModel."""
    defaults = {
        "id": 1,
        "name": "TestTenant",
        "slug": "test",
        "bot_token": "123456:ABC-DEF",
        "bot_username": "test_bot",
        "admin_group_id": -100123,
        "main_group_id": -100456,
        "business_type": "ceiling",
        "is_active": True,
        "billing_status": "active",
    }
    defaults.update(overrides)
    t = MagicMock()
    for k, v in defaults.items():
        setattr(t, k, v)
    return t


def _mock_redis_state(*, acquire_returns: bool = True) -> MagicMock:
    """Build a mock BotRegistryRedisState."""
    rs = MagicMock()
    rs.persist_state = AsyncMock()
    rs.load_state = AsyncMock(return_value=None)
    rs.remove_state = AsyncMock()
    rs.list_known_tenants = AsyncMock(return_value=set())
    rs.acquire_ownership = AsyncMock(return_value=acquire_returns)
    rs.release_ownership = AsyncMock()
    rs.renew_ownership = AsyncMock(return_value=True)
    rs.get_owner = AsyncMock(return_value=None)
    rs.send_heartbeat = AsyncMock()
    rs.get_running_tenants = AsyncMock(return_value=[])
    rs.get_orphaned_tenants = AsyncMock(return_value=[])
    rs.instance_id = "test_instance"
    return rs


def _make_registry_with_redis(
    *,
    acquire_returns: bool = True,
) -> tuple[BotRegistry, MagicMock]:
    """Create a BotRegistry with a mocked Redis state layer."""
    registry = BotRegistry()
    rs = _mock_redis_state(acquire_returns=acquire_returns)
    registry._redis_state = rs
    return registry, rs


async def _fake_register(registry: BotRegistry, tenant: MagicMock) -> None:
    """Simulate successful bot registration without network calls."""
    tid = tenant.id
    bot_id = 7770 + tid
    mock_bot = MagicMock()
    mock_bot.session = MagicMock()
    mock_bot.session.close = AsyncMock()
    registry._bots[bot_id] = mock_bot
    registry._tenant_map[bot_id] = tid
    registry._configs[tid] = TenantBotConfig(
        tenant_id=tid, bot_token=tenant.bot_token,
        bot_username="bot", admin_group_id=None,
        main_group_id=None, business_type="other",
    )
    registry._token_index[_hash_token(tenant.bot_token)] = tid
    state = BotRuntimeState(
        tenant_id=tid, tenant_name=tenant.name,
        status=BotStatus.RUNNING, bot_id=bot_id,
        last_started=datetime.now(timezone.utc),
    )
    registry._states[tid] = state
    await registry._sync_state_to_redis(state)


def _stub_register(registry: BotRegistry):
    """Return an async function that replaces _register_tenant for testing.

    Uses direct method replacement instead of patch.object to avoid
    AsyncMock wrapper issues with nested coroutine side effects.
    """
    async def _register(tenant):
        await _fake_register(registry, tenant)
    return _register


def _stub_failing_register(registry: BotRegistry):
    """Return an async _register_tenant that always fails."""
    async def _register(tenant):
        state = BotRuntimeState(
            tenant_id=tenant.id, tenant_name=tenant.name,
            status=BotStatus.FAILED, last_error="test_error",
        )
        registry._states[tenant.id] = state
        await registry._sync_state_to_redis(state)
    return _register


# ── State persistence tests ─────────────────────────────────────────────


class TestRedisStatePersistence:
    """State changes are synced to Redis."""

    async def test_load_from_db_persists_paused_state(self) -> None:
        """Inactive tenant state is persisted to Redis."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=1, is_active=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        await registry.load_from_db(session)

        rs.persist_state.assert_awaited()
        call_kwargs = rs.persist_state.call_args
        assert call_kwargs.kwargs["status"] == "paused"
        assert call_kwargs.kwargs["tenant_id"] == 1

    async def test_load_from_db_persists_running_state(self) -> None:
        """Successfully registered bot state is persisted to Redis."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=5)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        registry._register_tenant = _stub_register(registry)
        await registry.load_from_db(session)

        assert rs.persist_state.await_count >= 1
        assert registry.bot_count == 1

    async def test_stop_bot_syncs_stopped_state(self) -> None:
        """stop_bot persists STOPPED state and releases ownership."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=7)
        await _fake_register(registry, tenant)
        rs.persist_state.reset_mock()

        await registry.stop_bot(7)

        state = registry.get_bot_state(7)
        assert state is not None and state.status == BotStatus.STOPPED

        # Should persist STOPPED to Redis
        persist_calls = [
            c for c in rs.persist_state.call_args_list
            if c.kwargs.get("status") == "stopped"
        ]
        assert len(persist_calls) >= 1

        # Should release ownership
        rs.release_ownership.assert_awaited()

    async def test_failed_registration_persists_failed_state(self) -> None:
        """Failed bot registration persists FAILED to Redis."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=10)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        registry._register_tenant = _stub_failing_register(registry)
        await registry.load_from_db(session)

        persist_calls = [
            c for c in rs.persist_state.call_args_list
            if c.kwargs.get("status") == "failed"
        ]
        assert len(persist_calls) >= 1


# ── Ownership lock tests ────────────────────────────────────────────────


class TestOwnershipLocks:
    """Per-bot ownership locks prevent duplicate execution."""

    async def test_ownership_acquired_before_registration(self) -> None:
        """load_from_db acquires ownership before registering a bot."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        registry._register_tenant = _stub_register(registry)
        await registry.load_from_db(session)

        rs.acquire_ownership.assert_awaited_with(1)

    async def test_bot_skipped_when_owned_by_other(self) -> None:
        """Bot is not registered when another instance owns it."""
        registry, rs = _make_registry_with_redis(acquire_returns=False)
        tenant = _make_db_tenant(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        register_called = False

        async def should_not_be_called(t):
            nonlocal register_called
            register_called = True

        registry._register_tenant = should_not_be_called
        await registry.load_from_db(session)

        assert not register_called
        assert registry.bot_count == 0

    async def test_ownership_released_on_stop(self) -> None:
        """stop_bot releases ownership lock."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=3)
        await _fake_register(registry, tenant)
        rs.release_ownership.reset_mock()

        await registry.stop_bot(3)

        rs.release_ownership.assert_awaited_with(3)

    async def test_ownership_released_on_shutdown(self) -> None:
        """shutdown_all releases all ownership locks."""
        registry, rs = _make_registry_with_redis()
        t1 = _make_db_tenant(id=1, bot_token="tok1")
        t2 = _make_db_tenant(id=2, bot_token="tok2")
        await _fake_register(registry, t1)
        await _fake_register(registry, t2)
        rs.release_ownership.reset_mock()

        await registry.shutdown_all()

        # Should release ownership for both tenants
        released_ids = {c.args[0] for c in rs.release_ownership.call_args_list}
        assert 1 in released_ids
        assert 2 in released_ids

    async def test_start_bot_acquires_ownership(self) -> None:
        """start_bot acquires ownership before registering."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=5)
        session = AsyncMock()
        session.get = AsyncMock(return_value=tenant)

        registry._register_tenant = _stub_register(registry)
        status = await registry.start_bot(5, session)

        assert status == BotStatus.RUNNING
        rs.acquire_ownership.assert_awaited_with(5)

    async def test_start_bot_fails_if_owned_by_other(self) -> None:
        """start_bot returns FAILED if another instance owns the bot."""
        registry, rs = _make_registry_with_redis(acquire_returns=False)
        tenant = _make_db_tenant(id=5)
        session = AsyncMock()
        session.get = AsyncMock(return_value=tenant)

        status = await registry.start_bot(5, session)

        assert status == BotStatus.FAILED


# ── Recovery tests ───────────────────────────────────────────────────────


class TestRecoveryFromRedis:
    """Restart recovery re-creates bots from Redis state."""

    async def test_recover_orphaned_bots(self) -> None:
        """Orphaned bots (dead owner) are recovered."""
        registry, rs = _make_registry_with_redis()
        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 10, "status": "running", "bot_id": 7780},
        ]

        tenant = _make_db_tenant(id=10)
        session = AsyncMock()
        session.get = AsyncMock(return_value=tenant)

        registry._register_tenant = _stub_register(registry)
        counts = await registry.recover_from_redis(session)

        assert counts["recovered"] == 1
        assert registry.bot_count == 1

    async def test_recover_skips_inactive_tenant(self) -> None:
        """Recovery skips tenants that are now inactive in DB."""
        registry, rs = _make_registry_with_redis()
        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 20, "status": "running", "bot_id": 7790},
        ]

        tenant = _make_db_tenant(id=20, is_active=False)
        session = AsyncMock()
        session.get = AsyncMock(return_value=tenant)

        counts = await registry.recover_from_redis(session)

        assert counts["skipped"] == 1
        assert registry.bot_count == 0
        rs.release_ownership.assert_awaited()

    async def test_recover_skips_missing_tenant(self) -> None:
        """Recovery skips tenants no longer in DB."""
        registry, rs = _make_registry_with_redis()
        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 30, "status": "running", "bot_id": 7800},
        ]

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        counts = await registry.recover_from_redis(session)

        assert counts["skipped"] == 1
        rs.release_ownership.assert_awaited()

    async def test_recover_skips_already_managed(self) -> None:
        """Recovery skips bots already managed by this instance."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=40)
        await _fake_register(registry, tenant)

        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 40, "status": "running", "bot_id": 7810},
        ]

        session = AsyncMock()

        counts = await registry.recover_from_redis(session)

        assert counts["skipped"] == 1

    async def test_recover_no_redis_returns_zeros(self) -> None:
        """Recovery returns zeros when Redis is unavailable."""
        registry = BotRegistry()
        registry._redis_state = None

        # Patch _get_redis_state to return None
        with patch.object(registry, "_get_redis_state", return_value=None):
            session = AsyncMock()
            counts = await registry.recover_from_redis(session)

        assert counts == {"recovered": 0, "skipped": 0, "failed": 0}

    async def test_recover_handles_registration_failure(self) -> None:
        """Recovery counts failed re-registrations correctly."""
        registry, rs = _make_registry_with_redis()
        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 50, "status": "running", "bot_id": 7820},
        ]

        tenant = _make_db_tenant(id=50)
        session = AsyncMock()
        session.get = AsyncMock(return_value=tenant)

        async def failing_register(t):
            raise RuntimeError("network error")

        registry._register_tenant = failing_register
        counts = await registry.recover_from_redis(session)

        assert counts["failed"] == 1
        rs.release_ownership.assert_awaited()


# ── Heartbeat tests ──────────────────────────────────────────────────────


class TestHeartbeat:
    """Heartbeat renews liveness and ownership TTLs."""

    async def test_heartbeat_sends_and_renews(self) -> None:
        """heartbeat() sends heartbeat and renews all owned bot locks."""
        registry, rs = _make_registry_with_redis()
        t1 = _make_db_tenant(id=1, bot_token="tok1")
        t2 = _make_db_tenant(id=2, bot_token="tok2")
        await _fake_register(registry, t1)
        await _fake_register(registry, t2)
        rs.send_heartbeat.reset_mock()
        rs.renew_ownership.reset_mock()

        await registry.heartbeat()

        rs.send_heartbeat.assert_awaited_once()
        renewed_ids = {c.args[0] for c in rs.renew_ownership.call_args_list}
        assert 1 in renewed_ids
        assert 2 in renewed_ids

    async def test_heartbeat_noop_without_redis(self) -> None:
        """heartbeat() does nothing when Redis is unavailable."""
        registry = BotRegistry()
        with patch.object(registry, "_get_redis_state", return_value=None):
            await registry.heartbeat()  # Should not raise

    async def test_heartbeat_warns_on_lost_ownership(self) -> None:
        """heartbeat() logs warning when ownership is lost."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=1)
        await _fake_register(registry, tenant)
        rs.renew_ownership.return_value = False

        # Should not raise, just warn
        await registry.heartbeat()
        rs.renew_ownership.assert_awaited()


# ── Graceful degradation tests ───────────────────────────────────────────


class TestGracefulDegradation:
    """Registry works in single-instance mode when Redis is down."""

    async def test_load_works_without_redis(self) -> None:
        """load_from_db works even when Redis state init fails."""
        registry = BotRegistry()

        # Force _get_redis_state to return None (no Redis)
        registry._get_redis_state = lambda: None

        tenant = _make_db_tenant(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        registry._register_tenant = _stub_register(registry)
        await registry.load_from_db(session)

        assert registry.bot_count == 1

    async def test_stop_works_without_redis(self) -> None:
        """stop_bot works when Redis is unavailable."""
        registry = BotRegistry()
        registry._get_redis_state = lambda: None

        tenant = _make_db_tenant(id=2)
        await _fake_register(registry, tenant)
        result = await registry.stop_bot(2)
        assert result is True
        assert registry.bot_count == 0

    async def test_ownership_defaults_to_true_without_redis(self) -> None:
        """Without Redis, ownership is always granted (single-instance)."""
        registry = BotRegistry()
        with patch.object(registry, "_get_redis_state", return_value=None):
            result = await registry._try_acquire_ownership(99)
            assert result is True


# ── Instance ID uniqueness ───────────────────────────────────────────────


class TestInstanceId:
    """Each BotRegistry gets a unique instance ID."""

    def test_unique_ids(self) -> None:
        """Two registries have different instance IDs."""
        r1 = BotRegistry()
        r2 = BotRegistry()
        assert r1.instance_id != r2.instance_id

    def test_id_is_12_chars(self) -> None:
        """Instance ID is 12 hex chars."""
        r = BotRegistry()
        assert len(r.instance_id) == 12
        assert all(c in "0123456789abcdef" for c in r.instance_id)


# ── Multi-instance simulation ────────────────────────────────────────────


class TestMultiInstanceSimulation:
    """Simulate two instances trying to manage the same bot."""

    async def test_only_one_instance_registers_bot(self) -> None:
        """When two instances load the same tenant, only one registers."""
        # Instance A gets ownership
        registry_a, rs_a = _make_registry_with_redis(acquire_returns=True)
        # Instance B is denied ownership
        registry_b, rs_b = _make_registry_with_redis(acquire_returns=False)

        tenant = _make_db_tenant(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]

        session_a = AsyncMock()
        session_a.execute = AsyncMock(return_value=mock_result)
        session_b = AsyncMock()
        session_b.execute = AsyncMock(return_value=mock_result)

        registry_a._register_tenant = _stub_register(registry_a)
        await registry_a.load_from_db(session_a)

        registry_b._register_tenant = _stub_register(registry_b)
        await registry_b.load_from_db(session_b)

        assert registry_a.bot_count == 1
        assert registry_b.bot_count == 0

    async def test_instance_b_recovers_after_a_dies(self) -> None:
        """When instance A dies, instance B recovers its bots."""
        registry_b, rs_b = _make_registry_with_redis(acquire_returns=True)
        rs_b.get_orphaned_tenants.return_value = [
            {"tenant_id": 1, "status": "running", "bot_id": 7771},
        ]

        tenant = _make_db_tenant(id=1)
        session = AsyncMock()
        session.get = AsyncMock(return_value=tenant)

        registry_b._register_tenant = _stub_register(registry_b)
        counts = await registry_b.recover_from_redis(session)

        assert counts["recovered"] == 1
        assert registry_b.bot_count == 1


# ── Shutdown state sync ─────────────────────────────────────────────────


class TestShutdownSync:
    """shutdown_all persists STOPPED state and releases ownership."""

    async def test_shutdown_syncs_all_states(self) -> None:
        """All bot states are set to STOPPED in Redis."""
        registry, rs = _make_registry_with_redis()
        t1 = _make_db_tenant(id=1, bot_token="tok1")
        t2 = _make_db_tenant(id=2, bot_token="tok2")
        await _fake_register(registry, t1)
        await _fake_register(registry, t2)
        rs.persist_state.reset_mock()

        await registry.shutdown_all()

        stopped_calls = [
            c for c in rs.persist_state.call_args_list
            if c.kwargs.get("status") == "stopped"
        ]
        assert len(stopped_calls) == 2

        assert registry.bot_count == 0

    async def test_shutdown_releases_all_ownership(self) -> None:
        """All ownership locks are released on shutdown."""
        registry, rs = _make_registry_with_redis()
        t1 = _make_db_tenant(id=1, bot_token="tok1")
        await _fake_register(registry, t1)
        rs.release_ownership.reset_mock()

        await registry.shutdown_all()

        rs.release_ownership.assert_awaited()


# ── Resync + ownership tests ─────────────────────────────────────────────


class TestResyncOwnership:
    """resync_from_db respects ownership locks."""

    async def test_resync_acquires_ownership_for_new_bots(self) -> None:
        """resync_from_db acquires ownership before registering new bots."""
        registry, rs = _make_registry_with_redis()
        tenant = _make_db_tenant(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        registry._register_tenant = _stub_register(registry)
        summary = await registry.resync_from_db(session)

        assert summary["added"] == 1
        rs.acquire_ownership.assert_awaited()

    async def test_resync_skips_bot_owned_by_other(self) -> None:
        """resync_from_db skips bots owned by another instance."""
        registry, rs = _make_registry_with_redis(acquire_returns=False)
        tenant = _make_db_tenant(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        summary = await registry.resync_from_db(session)

        assert summary["added"] == 1  # counted as attempted
        assert registry.bot_count == 0  # but not actually registered


# ── Health check Redis sync tests ────────────────────────────────────────


class TestHealthCheckRedisSync:
    """Health check syncs state updates to Redis."""

    async def test_sync_state_to_redis_called(self) -> None:
        """_sync_state_to_redis persists state via Redis state layer."""
        registry, rs = _make_registry_with_redis()
        state = BotRuntimeState(
            tenant_id=1, tenant_name="Test",
            status=BotStatus.RUNNING, bot_id=7771,
        )

        await registry._sync_state_to_redis(state)

        rs.persist_state.assert_awaited_once()
        call_kwargs = rs.persist_state.call_args.kwargs
        assert call_kwargs["tenant_id"] == 1
        assert call_kwargs["status"] == "running"
        assert call_kwargs["bot_id"] == 7771

    async def test_sync_state_silent_on_redis_error(self) -> None:
        """_sync_state_to_redis silently handles Redis errors."""
        registry, rs = _make_registry_with_redis()
        rs.persist_state.side_effect = ConnectionError("Redis down")

        state = BotRuntimeState(
            tenant_id=1, tenant_name="Test",
            status=BotStatus.RUNNING,
        )

        # Should not raise
        await registry._sync_state_to_redis(state)


# ── Recovery from multiple orphaned bots ─────────────────────────────────


class TestRecoveryMultipleOrphans:
    """Recovery handles multiple orphaned bots correctly."""

    async def test_recover_multiple_orphaned_bots(self) -> None:
        """Multiple orphaned bots are all recovered."""
        registry, rs = _make_registry_with_redis()
        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 10, "status": "running", "bot_id": 7780},
            {"tenant_id": 20, "status": "running", "bot_id": 7790},
            {"tenant_id": 30, "status": "starting", "bot_id": 7800},
        ]

        tenants = {
            10: _make_db_tenant(id=10, bot_token="tok10"),
            20: _make_db_tenant(id=20, bot_token="tok20"),
            30: _make_db_tenant(id=30, bot_token="tok30"),
        }
        session = AsyncMock()
        session.get = AsyncMock(side_effect=lambda model, tid: tenants.get(tid))

        registry._register_tenant = _stub_register(registry)
        counts = await registry.recover_from_redis(session)

        assert counts["recovered"] == 3
        assert registry.bot_count == 3

    async def test_recover_partial_failure(self) -> None:
        """Some bots recover, some fail — counts are accurate."""
        registry, rs = _make_registry_with_redis()
        rs.get_orphaned_tenants.return_value = [
            {"tenant_id": 10, "status": "running", "bot_id": 7780},
            {"tenant_id": 20, "status": "running", "bot_id": 7790},
        ]

        tenants = {
            10: _make_db_tenant(id=10, bot_token="tok10"),
            20: _make_db_tenant(id=20, bot_token="tok20"),
        }
        session = AsyncMock()
        session.get = AsyncMock(side_effect=lambda model, tid: tenants.get(tid))

        call_count = 0

        async def register_with_one_failure(t):
            nonlocal call_count
            call_count += 1
            if t.id == 20:
                raise RuntimeError("network error")
            await _fake_register(registry, t)

        registry._register_tenant = register_with_one_failure
        counts = await registry.recover_from_redis(session)

        assert counts["recovered"] == 1
        assert counts["failed"] == 1
