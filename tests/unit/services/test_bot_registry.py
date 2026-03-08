"""Unit tests for BotRegistry.

Covers:
  1. load_from_db — active, inactive, expired, duplicate token handling
  2. Lookup methods — get_bot, get_tenant_id, get_tenant_config
  3. stop_bot — removes bot from active set
  4. Token deduplication — second tenant with same token is FAILED
  5. Paused billing — expired/suspended tenants are PAUSED
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from core.services.bot_registry import (
    BotRegistry,
    BotRuntimeState,
    BotStatus,
    TenantBotConfig,
    _hash_token,
)


def _make_db_tenant(**overrides) -> MagicMock:
    """Create a mock TenantModel for registry tests."""
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


class TestHashToken:
    """_hash_token produces stable, truncated SHA-256."""

    def test_deterministic(self) -> None:
        assert _hash_token("abc") == _hash_token("abc")

    def test_length_16(self) -> None:
        assert len(_hash_token("some-token")) == 16

    def test_different_tokens_differ(self) -> None:
        assert _hash_token("token-a") != _hash_token("token-b")


class TestLoadFromDb:
    """BotRegistry.load_from_db handles various tenant states."""

    def setup_method(self) -> None:
        self.registry = BotRegistry()

    async def test_inactive_tenant_is_paused(self) -> None:
        tenant = _make_db_tenant(id=1, is_active=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        await self.registry.load_from_db(session)

        state = self.registry.get_bot_state(1)
        assert state is not None
        assert state.status == BotStatus.PAUSED
        assert state.pause_reason == "inactive"
        assert self.registry.bot_count == 0

    async def test_expired_billing_is_paused(self) -> None:
        tenant = _make_db_tenant(id=2, billing_status="expired")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        await self.registry.load_from_db(session)

        state = self.registry.get_bot_state(2)
        assert state is not None
        assert state.status == BotStatus.PAUSED
        assert state.pause_reason == "billing_expired"

    async def test_suspended_billing_is_paused(self) -> None:
        tenant = _make_db_tenant(id=3, billing_status="suspended")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        await self.registry.load_from_db(session)

        state = self.registry.get_bot_state(3)
        assert state is not None
        assert state.status == BotStatus.PAUSED
        assert state.pause_reason == "billing_suspended"

    async def test_empty_token_skipped(self) -> None:
        tenant = _make_db_tenant(id=4, bot_token="  ")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        await self.registry.load_from_db(session)

        assert self.registry.bot_count == 0
        assert self.registry.get_bot_state(4) is None

    async def test_duplicate_token_is_failed(self) -> None:
        """Second tenant with same token should be FAILED."""
        token = "111:SAME-TOKEN"
        t1 = _make_db_tenant(id=10, bot_token=token)
        t2 = _make_db_tenant(id=20, bot_token=token)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [t1, t2]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        # Mock _register_tenant to simulate t1 succeeding
        async def fake_register(tenant):
            tid = tenant.id
            bot_id = 7770 + tid
            self.registry._bots[bot_id] = MagicMock()
            self.registry._tenant_map[bot_id] = tid
            self.registry._configs[tid] = TenantBotConfig(
                tenant_id=tid, bot_token=tenant.bot_token,
                bot_username="bot", admin_group_id=None,
                main_group_id=None, business_type="other",
            )
            self.registry._token_index[_hash_token(tenant.bot_token)] = tid
            self.registry._states[tid] = BotRuntimeState(
                tenant_id=tid, tenant_name=tenant.name,
                status=BotStatus.RUNNING, bot_id=bot_id,
            )

        with patch.object(self.registry, "_register_tenant", side_effect=fake_register):
            await self.registry.load_from_db(session)

        # t1 should be RUNNING, t2 should be FAILED with duplicate error
        s1 = self.registry.get_bot_state(10)
        s2 = self.registry.get_bot_state(20)
        assert s1 is not None and s1.status == BotStatus.RUNNING
        assert s2 is not None and s2.status == BotStatus.FAILED
        assert "duplicate_token" in (s2.last_error or "")

    async def test_successful_registration(self) -> None:
        tenant = _make_db_tenant(id=5)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        async def fake_register(t):
            self.registry._states[t.id] = BotRuntimeState(
                tenant_id=t.id, tenant_name=t.name,
                status=BotStatus.RUNNING, bot_id=9999,
            )
            self.registry._bots[9999] = MagicMock()
            self.registry._tenant_map[9999] = t.id

        with patch.object(self.registry, "_register_tenant", side_effect=fake_register):
            await self.registry.load_from_db(session)

        assert self.registry.bot_count == 1
        s = self.registry.get_bot_state(5)
        assert s is not None and s.status == BotStatus.RUNNING


class TestLookups:
    """Lookup methods return correct data after registration."""

    def setup_method(self) -> None:
        self.registry = BotRegistry()
        # Manually register a bot
        bot_id = 12345
        tenant_id = 1
        self.registry._bots[bot_id] = MagicMock()
        self.registry._tenant_map[bot_id] = tenant_id
        self.registry._configs[tenant_id] = TenantBotConfig(
            tenant_id=tenant_id, bot_token="tok",
            bot_username="mybot", admin_group_id=-100,
            main_group_id=-200, business_type="ceiling",
        )

    def test_get_bot_returns_bot(self) -> None:
        assert self.registry.get_bot(12345) is not None

    def test_get_bot_missing(self) -> None:
        assert self.registry.get_bot(99999) is None

    def test_get_tenant_id(self) -> None:
        assert self.registry.get_tenant_id(12345) == 1

    def test_get_tenant_id_missing(self) -> None:
        assert self.registry.get_tenant_id(99999) is None

    def test_get_tenant_config(self) -> None:
        cfg = self.registry.get_tenant_config(1)
        assert cfg is not None
        assert cfg.bot_username == "mybot"
        assert cfg.business_type == "ceiling"

    def test_get_config_by_bot_id(self) -> None:
        cfg = self.registry.get_config_by_bot_id(12345)
        assert cfg is not None
        assert cfg.tenant_id == 1

    def test_get_config_by_bot_id_missing(self) -> None:
        assert self.registry.get_config_by_bot_id(99999) is None

    def test_all_bots(self) -> None:
        assert len(self.registry.all_bots()) == 1

    def test_bot_count(self) -> None:
        assert self.registry.bot_count == 1


class TestStopBot:
    """stop_bot removes bot from active set and marks STOPPED."""

    def setup_method(self) -> None:
        self.registry = BotRegistry()

    async def test_stop_removes_and_marks_stopped(self) -> None:
        bot_id = 111
        tenant_id = 7
        mock_bot = AsyncMock()
        self.registry._bots[bot_id] = mock_bot
        self.registry._tenant_map[bot_id] = tenant_id
        self.registry._configs[tenant_id] = TenantBotConfig(
            tenant_id=tenant_id, bot_token="tok",
            bot_username="b", admin_group_id=None,
            main_group_id=None, business_type="other",
        )
        self.registry._token_index[_hash_token("tok")] = tenant_id
        self.registry._states[tenant_id] = BotRuntimeState(
            tenant_id=tenant_id, tenant_name="T",
            status=BotStatus.RUNNING, bot_id=bot_id,
        )

        result = await self.registry.stop_bot(tenant_id)

        assert result is True
        assert self.registry.bot_count == 0
        assert self.registry.get_bot(bot_id) is None
        state = self.registry.get_bot_state(tenant_id)
        assert state is not None and state.status == BotStatus.STOPPED
        mock_bot.session.close.assert_awaited_once()

    async def test_stop_nonexistent_returns_false(self) -> None:
        result = await self.registry.stop_bot(999)
        assert result is False


class TestShutdownAll:
    """shutdown_all closes all bots and clears collections."""

    def setup_method(self) -> None:
        self.registry = BotRegistry()

    async def test_shutdown_clears_everything(self) -> None:
        mock_bot = AsyncMock()
        self.registry._bots[1] = mock_bot
        self.registry._tenant_map[1] = 10
        self.registry._configs[10] = TenantBotConfig(
            tenant_id=10, bot_token="t", bot_username="b",
            admin_group_id=None, main_group_id=None, business_type="o",
        )
        self.registry._states[10] = BotRuntimeState(
            tenant_id=10, tenant_name="T", status=BotStatus.RUNNING,
        )

        await self.registry.shutdown_all()

        assert self.registry.bot_count == 0
        assert len(self.registry._tenant_map) == 0
        assert len(self.registry._configs) == 0
        state = self.registry.get_bot_state(10)
        assert state is not None and state.status == BotStatus.STOPPED
        mock_bot.session.close.assert_awaited_once()


class TestListStatus:
    """list_status returns status summary for tracked bots."""

    def setup_method(self) -> None:
        self.registry = BotRegistry()

    def test_returns_correct_summary(self) -> None:
        self.registry._states[1] = BotRuntimeState(
            tenant_id=1, tenant_name="A",
            status=BotStatus.RUNNING, bot_id=100,
        )
        self.registry._states[2] = BotRuntimeState(
            tenant_id=2, tenant_name="B",
            status=BotStatus.PAUSED, pause_reason="billing_expired",
        )
        self.registry._configs[1] = TenantBotConfig(
            tenant_id=1, bot_token="t", bot_username="abot",
            admin_group_id=None, main_group_id=None, business_type="o",
        )

        statuses = self.registry.list_status()
        assert len(statuses) == 2

        by_tid = {s["tenant_id"]: s for s in statuses}
        assert by_tid[1]["status"] == "running"
        assert by_tid[1]["bot_username"] == "abot"
        assert by_tid[2]["status"] == "paused"
        assert by_tid[2]["bot_username"] is None
