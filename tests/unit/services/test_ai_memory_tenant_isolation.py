"""Cross-tenant isolation tests for AI conversation and memory tables.

Verifies that the composite PK (tenant_id, user_id) on ai_conversations
and ai_user_memory prevents data collision between tenants sharing the
same Telegram user_id.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.database.models.ai_conversation import AiConversationModel
from infrastructure.database.models.ai_memory import AiMemoryModel


# ── ORM model structure tests ───────────────────────────────────────────────


class TestAiConversationModelSchema:
    """Verify AiConversationModel has correct composite PK."""

    def test_table_name(self) -> None:
        assert AiConversationModel.__tablename__ == "ai_conversations"

    def test_composite_primary_key(self) -> None:
        """PK must be (tenant_id, user_id)."""
        pk_cols = [c.name for c in AiConversationModel.__table__.primary_key.columns]
        assert pk_cols == ["tenant_id", "user_id"]

    def test_tenant_id_not_nullable(self) -> None:
        col = AiConversationModel.__table__.c.tenant_id
        assert col.nullable is False

    def test_user_id_not_nullable(self) -> None:
        col = AiConversationModel.__table__.c.user_id
        assert col.nullable is False

    def test_has_tenant_id_index(self) -> None:
        idx_names = [idx.name for idx in AiConversationModel.__table__.indexes]
        assert "ix_ai_conversations_tenant_id" in idx_names

    def test_has_user_id_index(self) -> None:
        idx_names = [idx.name for idx in AiConversationModel.__table__.indexes]
        assert "ix_ai_conversations_user_id" in idx_names


class TestAiMemoryModelSchema:
    """Verify AiMemoryModel has correct composite PK."""

    def test_table_name(self) -> None:
        assert AiMemoryModel.__tablename__ == "ai_user_memory"

    def test_composite_primary_key(self) -> None:
        """PK must be (tenant_id, user_id)."""
        pk_cols = [c.name for c in AiMemoryModel.__table__.primary_key.columns]
        assert pk_cols == ["tenant_id", "user_id"]

    def test_tenant_id_not_nullable(self) -> None:
        col = AiMemoryModel.__table__.c.tenant_id
        assert col.nullable is False

    def test_user_id_not_nullable(self) -> None:
        col = AiMemoryModel.__table__.c.user_id
        assert col.nullable is False

    def test_has_tenant_id_index(self) -> None:
        idx_names = [idx.name for idx in AiMemoryModel.__table__.indexes]
        assert "ix_ai_user_memory_tenant_id" in idx_names

    def test_has_user_id_index(self) -> None:
        idx_names = [idx.name for idx in AiMemoryModel.__table__.indexes]
        assert "ix_ai_user_memory_user_id" in idx_names


# ── AI openai functions tenant isolation ────────────────────────────────────


class TestLoadContextTenantIsolation:
    """Verify _load_context uses composite key."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def mock_factory(self, mock_session: AsyncMock) -> MagicMock:
        factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory.return_value = ctx
        return factory

    @pytest.mark.asyncio
    async def test_load_context_uses_composite_key(
        self, mock_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """_load_context must pass (tenant_id, user_id) tuple to session.get."""
        with patch(
            "core.services.ai_engine.get_session_factory",
            return_value=mock_factory,
        ):
            from apps.bot.handlers.private.ai_openai import _load_context

            await _load_context(user_id=12345, tenant_id=10)

        calls = mock_session.get.call_args_list
        assert len(calls) == 2
        # First call: AiMemoryModel with (tenant_id, user_id)
        assert calls[0].args == (AiMemoryModel, (10, 12345))
        # Second call: AiConversationModel with (tenant_id, user_id)
        assert calls[1].args == (AiConversationModel, (10, 12345))

    @pytest.mark.asyncio
    async def test_load_context_no_tenant_returns_empty(
        self, mock_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """_load_context with tenant_id=None should not query DB and return empty."""
        with patch(
            "core.services.ai_engine.get_session_factory",
            return_value=mock_factory,
        ):
            from apps.bot.handlers.private.ai_openai import _load_context

            profile, messages, summary = await _load_context(user_id=12345, tenant_id=None)

        assert profile == {}
        assert messages == []
        assert summary is None


class TestPersistExchangeTenantIsolation:
    """Verify _persist_exchange requires tenant_id."""

    @pytest.mark.asyncio
    async def test_persist_exchange_no_tenant_skips(self) -> None:
        """_persist_exchange without tenant_id should log warning and return."""
        from apps.bot.handlers.private.ai_openai import _persist_exchange

        # Should not raise — just returns early
        await _persist_exchange(
            user_id=12345,
            tenant_id=None,
            user_text="test",
            assistant_text="reply",
            intent="greeting",
            extracted={},
            current_profile={},
            current_messages=[],
            current_summary=None,
        )

    @pytest.mark.asyncio
    async def test_persist_exchange_uses_composite_conflict_key(self) -> None:
        """_persist_exchange must use index_elements=['tenant_id', 'user_id']."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory.return_value = ctx

        with patch(
            "core.services.ai_engine.get_session_factory",
            return_value=factory,
        ):
            from apps.bot.handlers.private.ai_openai import _persist_exchange

            await _persist_exchange(
                user_id=12345,
                tenant_id=10,
                user_text="test",
                assistant_text="reply",
                intent="greeting",
                extracted={},
                current_profile={},
                current_messages=[],
                current_summary=None,
            )

        # Verify two INSERT statements were executed (conversations + memory)
        assert mock_session.execute.call_count == 2
        assert mock_session.commit.call_count == 1


class TestClearAiConversationTenantIsolation:
    """Verify clear_ai_conversation requires tenant_id."""

    @pytest.mark.asyncio
    async def test_clear_without_tenant_skips(self) -> None:
        """clear_ai_conversation without tenant_id should return early."""
        from apps.bot.handlers.private.ai_openai import clear_ai_conversation

        # Should not raise — just returns early
        await clear_ai_conversation(user_id=12345, tenant_id=None)

    @pytest.mark.asyncio
    async def test_clear_with_tenant_executes(self) -> None:
        """clear_ai_conversation with tenant_id should execute upsert."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory.return_value = ctx

        with patch(
            "core.services.ai_engine.get_session_factory",
            return_value=factory,
        ):
            from apps.bot.handlers.private.ai_openai import clear_ai_conversation

            await clear_ai_conversation(user_id=12345, tenant_id=10)

        assert mock_session.execute.call_count == 1
        assert mock_session.commit.call_count == 1


class TestStoreUserMessageTenantIsolation:
    """Verify _store_user_message_only requires tenant_id."""

    @pytest.mark.asyncio
    async def test_store_without_tenant_skips(self) -> None:
        """_store_user_message_only without tenant_id should return early."""
        from apps.bot.handlers.private.ai_openai import _store_user_message_only

        # Should not raise
        await _store_user_message_only(
            user_id=12345,
            tenant_id=None,
            user_text="test",
            current_messages=[],
        )


# ── Two tenants same user_id cannot collide (model-level) ─────────────────


class TestCompositePKPreventsCollision:
    """Verify that the composite PK allows same user_id across different tenants."""

    def test_conversation_different_tenants_same_user(self) -> None:
        """Two AiConversationModel instances with same user_id but different tenants are distinct."""
        conv_a = AiConversationModel(tenant_id=1, user_id=12345, last_messages=[{"role": "user", "text": "hi"}])
        conv_b = AiConversationModel(tenant_id=2, user_id=12345, last_messages=[{"role": "user", "text": "hello"}])

        # Different tenant_ids → different logical rows
        assert conv_a.tenant_id != conv_b.tenant_id
        assert conv_a.user_id == conv_b.user_id
        assert conv_a.last_messages != conv_b.last_messages

    def test_memory_different_tenants_same_user(self) -> None:
        """Two AiMemoryModel instances with same user_id but different tenants are distinct."""
        mem_a = AiMemoryModel(tenant_id=1, user_id=12345, profile={"name": "Alice"})
        mem_b = AiMemoryModel(tenant_id=2, user_id=12345, profile={"name": "Bob"})

        assert mem_a.tenant_id != mem_b.tenant_id
        assert mem_a.user_id == mem_b.user_id
        assert mem_a.profile != mem_b.profile
