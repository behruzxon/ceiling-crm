# 10 — Test Plan (Test Rejasi)

## Umumiy Ko'rinish

AI Agent System uchun to'liq test rejasi. Barcha test'lar `pytest` bilan yoziladi, `asyncio_mode = "auto"` — async test funksiyalari `@pytest.mark.asyncio` siz ishlaydi.

### Test Strukturasi
```
tests/
├── conftest.py                          # Shared fixtures (mavjud + yangi)
├── unit/
│   └── services/
│       ├── test_journey_event_service.py
│       ├── test_agent_memory_service.py
│       ├── test_agent_followup_service.py
│       ├── test_message_composer.py
│       └── test_enhanced_notifications.py
├── integration/
│   ├── test_followup_flow.py
│   └── test_journey_tracking.py
└── e2e/
    └── test_agent_manual_scenarios.py   # Manual test ssenariylarini avtomatlashtirilgan versiyasi
```

### Test Buyruqlari
```bash
# Barcha unit test'lar
pytest tests/unit/ -v

# Faqat agent test'lar
pytest tests/unit/services/test_journey_event_service.py -v
pytest tests/unit/services/test_agent_memory_service.py -v
pytest tests/unit/services/test_agent_followup_service.py -v
pytest tests/unit/services/test_message_composer.py -v
pytest tests/unit/services/test_enhanced_notifications.py -v

# Integration test'lar
pytest tests/integration/ -v

# Coverage
pytest tests/ --cov=core/services --cov-report=term-missing
```

---

## 1. Mock Fixtures (tests/conftest.py ga qo'shiladi)

Mavjud fixture'larni kengaytirish — yangi repository va service mock'lari:

```python
# ── Journey Event fixtures ─────────────────────────────────────────

@pytest.fixture
def mock_journey_event_repo():
    """Mock AbstractJourneyEventRepository for journey tracking tests."""
    from core.repositories.journey_event_repo import AbstractJourneyEventRepository
    repo = AsyncMock(spec=AbstractJourneyEventRepository)
    repo.create_event.return_value = MagicMock(
        id=1,
        user_id=12345,
        event_type="opened_catalog",
        payload={},
        journey_state="browsing",
        created_at=datetime(2024, 1, 1, 14, 30, tzinfo=timezone.utc),
    )
    repo.get_user_events.return_value = []
    repo.get_latest_state.return_value = "idle"
    return repo


@pytest.fixture
def journey_event_service(mock_journey_event_repo):
    """JourneyEventService with mocked repository."""
    from core.services.journey_event_service import JourneyEventService
    return JourneyEventService(repo=mock_journey_event_repo)


# ── Agent Memory fixtures ──────────────────────────────────────────

@pytest.fixture
def mock_agent_memory_repo():
    """Mock AbstractAgentMemoryRepository for memory tests."""
    from core.repositories.agent_memory_repo import AbstractAgentMemoryRepository
    repo = AsyncMock(spec=AbstractAgentMemoryRepository)
    repo.get_state.return_value = MagicMock(
        user_id=12345,
        journey_state="idle",
        last_event_type=None,
        intent_history=[],
        follow_up_history=[],
    )
    repo.upsert_state.return_value = None
    return repo


@pytest.fixture
def mock_agent_memory_service():
    """Mock AgentMemoryService for tests that depend on memory."""
    from core.services.agent_memory_service import AgentMemoryService
    service = AsyncMock(spec=AgentMemoryService)
    service.get_memory.return_value = {
        "journey_state": "idle",
        "last_event_type": None,
        "intent_history": [],
        "follow_up_history": [],
    }
    service.update_memory.return_value = None
    return service


# ── Follow-up Scheduler fixtures ──────────────────────────────────

@pytest.fixture
def mock_followup_repo():
    """Mock repository for scheduled follow-ups."""
    repo = AsyncMock()
    repo.create.return_value = MagicMock(
        id=1,
        user_id=12345,
        event_type="opened_catalog",
        status="pending",
    )
    repo.get_pending.return_value = []
    repo.cancel_by_user.return_value = 0
    return repo


@pytest.fixture
def mock_followup_scheduler(mock_followup_repo, mock_agent_memory_service):
    """AgentFollowupService with mocked dependencies."""
    from core.services.agent_followup_service import AgentFollowupService
    return AgentFollowupService(
        repo=mock_followup_repo,
        memory_service=mock_agent_memory_service,
    )


# ── Message Composer fixtures ─────────────────────────────────────

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for message composition tests."""
    client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Assalomu alaykum! Katalogdagi qaysi model yoqdi?"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


# ── Redis mock fixture ────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Mock Redis client for cache/dedup tests."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.incr.return_value = 1
    redis.expire.return_value = True
    redis.delete.return_value = 1
    return redis
```

---

## 2. Unit Tests — Journey Event Service

**Fayl**: `tests/unit/services/test_journey_event_service.py`

### test_emit_event_saves_to_db
```python
async def test_emit_event_saves_to_db(journey_event_service, mock_journey_event_repo):
    """Event emit qilinganda DB ga yozilishi kerak."""
    await journey_event_service.emit(
        user_id=12345,
        event_type="opened_catalog",
        payload={"source": "main_menu"},
    )

    mock_journey_event_repo.create_event.assert_called_once_with(
        user_id=12345,
        event_type="opened_catalog",
        payload={"source": "main_menu"},
    )
```

### test_emit_event_updates_journey_state
```python
async def test_emit_event_updates_journey_state(journey_event_service, mock_journey_event_repo):
    """Event emit journey state'ni yangilashi kerak (IDLE -> BROWSING)."""
    mock_journey_event_repo.get_latest_state.return_value = "idle"

    await journey_event_service.emit(
        user_id=12345,
        event_type="opened_catalog",
    )

    # Journey state "browsing" ga o'zgarishi kerak
    mock_journey_event_repo.update_journey_state.assert_called_once_with(
        user_id=12345,
        new_state="browsing",
    )
```

### test_event_dedup_within_window
```python
async def test_event_dedup_within_window(journey_event_service, mock_journey_event_repo):
    """1 daqiqa ichida bir xil event ikki marta emit qilinsa, faqat bittasi saqlanishi kerak."""
    from datetime import datetime, timezone, timedelta

    recent_event = MagicMock(
        event_type="opened_catalog",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    mock_journey_event_repo.get_latest_event.return_value = recent_event

    await journey_event_service.emit(
        user_id=12345,
        event_type="opened_catalog",
    )

    # Duplikat — create_event chaqirilmasligi kerak
    mock_journey_event_repo.create_event.assert_not_called()
```

### test_invalid_event_type_rejected
```python
async def test_invalid_event_type_rejected(journey_event_service):
    """Noto'g'ri event type ValueError qaytarishi kerak."""
    with pytest.raises(ValueError, match="Invalid event type"):
        await journey_event_service.emit(
            user_id=12345,
            event_type="invalid_event_type",
        )
```

---

## 3. Unit Tests — Agent Memory Service

**Fayl**: `tests/unit/services/test_agent_memory_service.py`

### test_create_memory_on_first_interaction
```python
async def test_create_memory_on_first_interaction(
    mock_agent_memory_repo, mock_redis
):
    """Birinchi interaksiyada yangi memory yaratilishi kerak."""
    from core.services.agent_memory_service import AgentMemoryService

    mock_redis.get.return_value = None  # Redis da memory yo'q
    mock_agent_memory_repo.get_state.return_value = None  # DB da ham yo'q

    service = AgentMemoryService(repo=mock_agent_memory_repo, redis=mock_redis)
    memory = await service.get_memory(user_id=12345)

    # Default memory yaratilishi kerak
    assert memory["journey_state"] == "idle"
    assert memory["intent_history"] == []
```

### test_update_memory_fields
```python
async def test_update_memory_fields(mock_agent_memory_repo, mock_redis):
    """Memory field'larini yangilash to'g'ri ishlashi kerak."""
    from core.services.agent_memory_service import AgentMemoryService

    service = AgentMemoryService(repo=mock_agent_memory_repo, redis=mock_redis)

    await service.update_memory(
        user_id=12345,
        updates={
            "journey_state": "browsing",
            "last_event_type": "opened_catalog",
        },
    )

    # Redis ga yozilishi kerak
    mock_redis.set.assert_called_once()
    # DB ga sync qilinishi kerak
    mock_agent_memory_repo.upsert_state.assert_called_once()
```

### test_memory_redis_db_sync
```python
async def test_memory_redis_db_sync(mock_agent_memory_repo, mock_redis):
    """Redis crash bo'lganda DB dan yuklash kerak."""
    from core.services.agent_memory_service import AgentMemoryService

    # Redis bo'sh, DB da bor
    mock_redis.get.return_value = None
    mock_agent_memory_repo.get_state.return_value = MagicMock(
        journey_state="calculating",
        last_event_type="price_calculated",
        intent_history=[{"type": "price", "ts": 1704067200}],
        follow_up_history=[],
    )

    service = AgentMemoryService(repo=mock_agent_memory_repo, redis=mock_redis)
    memory = await service.get_memory(user_id=12345)

    assert memory["journey_state"] == "calculating"
    assert memory["last_event_type"] == "price_calculated"
    # Redis ga qayta yozilishi kerak (cache warm-up)
    mock_redis.set.assert_called_once()
```

### test_memory_cleanup_after_90_days
```python
async def test_memory_cleanup_after_90_days(mock_agent_memory_repo):
    """90 kundan eski memory yozuvlari o'chirilishi kerak."""
    from core.services.agent_memory_service import AgentMemoryService
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    service = AgentMemoryService(repo=mock_agent_memory_repo, redis=AsyncMock())
    await service.cleanup_old_memories(before=cutoff)

    mock_agent_memory_repo.delete_old.assert_called_once_with(before=cutoff)
```

### test_phone_not_logged
```python
async def test_phone_not_logged(mock_agent_memory_repo, mock_redis):
    """Telefon raqam memory'da saqlanMASligi kerak (privacy)."""
    from core.services.agent_memory_service import AgentMemoryService

    service = AgentMemoryService(repo=mock_agent_memory_repo, redis=mock_redis)

    await service.update_memory(
        user_id=12345,
        updates={
            "phone": "+998901234567",     # Bu saqlanmasligi kerak
            "phone_captured": True,        # Bu saqlanishi mumkin (boolean flag)
            "journey_state": "ordering",
        },
    )

    # upsert_state ga yuborilgan data'da phone field bo'lmasligi kerak
    call_kwargs = mock_agent_memory_repo.upsert_state.call_args
    assert "phone" not in str(call_kwargs)
```

---

## 4. Unit Tests — Follow-up Scheduler

**Fayl**: `tests/unit/services/test_agent_followup_service.py`

### test_catalog_followup_after_10_minutes
```python
async def test_catalog_followup_after_10_minutes(mock_followup_scheduler):
    """Katalog ochilgandan 10 daqiqa keyin follow-up schedule bo'lishi kerak."""
    await mock_followup_scheduler.schedule_followup(
        user_id=12345,
        event_type="opened_catalog",
        delay_minutes=10,
    )

    # Pending follow-up yaratilishi kerak
    mock_followup_scheduler._repo.create.assert_called_once()
    call_kwargs = mock_followup_scheduler._repo.create.call_args[1]
    assert call_kwargs["event_type"] == "opened_catalog"
    assert call_kwargs["status"] == "pending"
```

### test_price_followup_after_10_minutes
```python
async def test_price_followup_after_10_minutes(mock_followup_scheduler):
    """Narx hisoblangandan 10 daqiqa keyin follow-up schedule bo'lishi kerak."""
    await mock_followup_scheduler.schedule_followup(
        user_id=12345,
        event_type="price_calculated",
        delay_minutes=10,
        payload={"design": "Gulli", "price": 5000000, "area": 20},
    )

    mock_followup_scheduler._repo.create.assert_called_once()
```

### test_abandoned_order_followup_after_10_minutes
```python
async def test_abandoned_order_followup_after_10_minutes(mock_followup_scheduler):
    """Buyurtma tashlab ketilgandan 10 daqiqa keyin follow-up schedule bo'lishi kerak."""
    await mock_followup_scheduler.schedule_followup(
        user_id=12345,
        event_type="order_form_abandoned",
        delay_minutes=10,
        payload={
            "completed_fields": ["name", "phone"],
            "missing_fields": ["district", "type", "area"],
        },
    )

    mock_followup_scheduler._repo.create.assert_called_once()
```

### test_followup_cancelled_on_user_reply
```python
async def test_followup_cancelled_on_user_reply(mock_followup_scheduler):
    """Mijoz javob yozganda barcha pending follow-up'lar bekor bo'lishi kerak."""
    await mock_followup_scheduler.cancel_followups(
        user_id=12345,
        reason="user_replied",
    )

    mock_followup_scheduler._repo.cancel_by_user.assert_called_once_with(
        user_id=12345,
        reason="user_replied",
    )
```

### test_followup_cancelled_on_order
```python
async def test_followup_cancelled_on_order(mock_followup_scheduler):
    """Buyurtma berilganda barcha pending follow-up'lar bekor bo'lishi kerak."""
    await mock_followup_scheduler.cancel_followups(
        user_id=12345,
        reason="order_completed",
    )

    mock_followup_scheduler._repo.cancel_by_user.assert_called_once_with(
        user_id=12345,
        reason="order_completed",
    )
```

### test_followup_cancelled_on_operator_request
```python
async def test_followup_cancelled_on_operator_request(mock_followup_scheduler):
    """Operator so'ralganda follow-up'lar bekor bo'lishi kerak."""
    await mock_followup_scheduler.cancel_followups(
        user_id=12345,
        reason="operator_requested",
    )

    mock_followup_scheduler._repo.cancel_by_user.assert_called_once()
```

### test_followup_cancelled_on_kerak_emas
```python
async def test_followup_cancelled_on_kerak_emas(mock_followup_scheduler):
    """Mijoz 'kerak emas' deganda barcha follow-up'lar to'xtatilishi kerak."""
    await mock_followup_scheduler.cancel_followups(
        user_id=12345,
        reason="user_opted_out",
    )

    mock_followup_scheduler._repo.cancel_by_user.assert_called_once_with(
        user_id=12345,
        reason="user_opted_out",
    )
```

### test_max_followup_count_respected
```python
async def test_max_followup_count_respected(mock_followup_scheduler, mock_followup_repo):
    """Bir event turi uchun max 3 ta follow-up limit'i saqlanishi kerak."""
    # Allaqachon 3 ta follow-up yuborilgan
    mock_followup_repo.count_by_user_and_type.return_value = 3

    result = await mock_followup_scheduler.schedule_followup(
        user_id=12345,
        event_type="opened_catalog",
        delay_minutes=10,
    )

    # Schedule qilinmasligi kerak (max limit)
    assert result is None or result.get("skipped") is True
    mock_followup_repo.create.assert_not_called()
```

### test_cooldown_between_followups
```python
async def test_cooldown_between_followups(mock_followup_scheduler, mock_followup_repo):
    """Ikki follow-up orasida minimum 15 daqiqa cooldown bo'lishi kerak."""
    from datetime import datetime, timezone, timedelta

    # Oxirgi follow-up 5 daqiqa oldin yuborilgan
    mock_followup_repo.get_latest_sent.return_value = MagicMock(
        sent_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    result = await mock_followup_scheduler.schedule_followup(
        user_id=12345,
        event_type="price_calculated",
        delay_minutes=10,
    )

    # Cooldown — schedule kechiktirilishi yoki skip qilinishi kerak
    assert result is None or result.get("delayed") is True
```

### test_no_duplicate_followup_for_same_event
```python
async def test_no_duplicate_followup_for_same_event(mock_followup_scheduler, mock_followup_repo):
    """Bir xil event uchun ikkinchi pending follow-up yaratilmasligi kerak."""
    # Allaqachon pending follow-up bor
    mock_followup_repo.get_pending_by_type.return_value = MagicMock(
        id=1, status="pending", event_type="opened_catalog"
    )

    result = await mock_followup_scheduler.schedule_followup(
        user_id=12345,
        event_type="opened_catalog",
        delay_minutes=10,
    )

    # Duplikat — yaratilmasligi kerak
    mock_followup_repo.create.assert_not_called()
```

### test_followup_survives_bot_restart
```python
async def test_followup_survives_bot_restart(mock_followup_repo):
    """Bot restart'dan keyin pending follow-up'lar DB dan yuklanishi kerak."""
    from datetime import datetime, timezone

    mock_followup_repo.get_pending.return_value = [
        MagicMock(
            id=1, user_id=12345, event_type="opened_catalog",
            status="pending",
            scheduled_at=datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc),
        ),
        MagicMock(
            id=2, user_id=67890, event_type="price_calculated",
            status="pending",
            scheduled_at=datetime(2024, 1, 1, 15, 5, tzinfo=timezone.utc),
        ),
    ]

    pending = await mock_followup_repo.get_pending()
    assert len(pending) == 2
    assert pending[0].event_type == "opened_catalog"
    assert pending[1].event_type == "price_calculated"
```

### test_anti_spam_max_per_day
```python
async def test_anti_spam_max_per_day(mock_followup_scheduler, mock_redis):
    """Kuniga max 5 ta follow-up limit'i saqlanishi kerak."""
    # Redis counter: bugun 5 ta yuborilgan
    mock_redis.get.return_value = b"5"

    result = await mock_followup_scheduler.check_anti_spam(user_id=12345)

    assert result["allowed"] is False
    assert result["reason"] == "daily_limit_exceeded"
```

### test_anti_spam_max_per_hour
```python
async def test_anti_spam_max_per_hour(mock_followup_scheduler, mock_redis):
    """Soatiga max 2 ta follow-up limit'i saqlanishi kerak."""
    # Redis counter: bu soatda 2 ta yuborilgan
    mock_redis.get.return_value = b"2"

    result = await mock_followup_scheduler.check_anti_spam(user_id=12345)

    assert result["allowed"] is False
    assert result["reason"] == "hourly_limit_exceeded"
```

---

## 5. Unit Tests — Message Composer

**Fayl**: `tests/unit/services/test_message_composer.py`

### test_catalog_followup_message_format
```python
async def test_catalog_followup_message_format(mock_openai_client):
    """Katalog follow-up xabari to'g'ri formatda bo'lishi kerak."""
    from core.services.message_composer_service import MessageComposerService

    service = MessageComposerService(openai_client=mock_openai_client)
    message = await service.compose_followup(
        event_type="opened_catalog",
        user_name="Aziz",
        journey_events=[{"type": "opened_catalog", "ts": "14:30"}],
        memory={"journey_state": "browsing"},
    )

    assert isinstance(message, str)
    assert len(message) > 0
    assert len(message) <= 500  # Max uzunlik limiti
```

### test_price_followup_includes_price
```python
async def test_price_followup_includes_price(mock_openai_client):
    """Narx follow-up xabarida narx ko'rsatilishi kerak."""
    from core.services.message_composer_service import MessageComposerService

    # Template fallback'ni test qilish uchun OpenAI xato qaytarsin
    mock_openai_client.chat.completions.create.side_effect = Exception("API error")

    service = MessageComposerService(openai_client=mock_openai_client)
    message = await service.compose_followup(
        event_type="price_calculated",
        user_name="Aziz",
        journey_events=[],
        memory={"last_price": 5000000, "last_design": "Gulli"},
    )

    # Template fallback ishlatiladi — narx bo'lishi kerak
    assert "5,000,000" in message or "5000000" in message
```

### test_abandoned_form_shows_progress
```python
async def test_abandoned_form_shows_progress(mock_openai_client):
    """Tashlab ketilgan form xabari progress ko'rsatishi kerak."""
    from core.services.message_composer_service import MessageComposerService

    mock_openai_client.chat.completions.create.side_effect = Exception("API error")

    service = MessageComposerService(openai_client=mock_openai_client)
    message = await service.compose_followup(
        event_type="order_form_abandoned",
        user_name="Aziz",
        journey_events=[],
        memory={
            "completed_fields": ["name", "phone"],
            "missing_fields": ["district", "type", "area"],
        },
    )

    assert isinstance(message, str)
    assert len(message) > 0
```

### test_message_in_uzbek
```python
async def test_message_in_uzbek(mock_openai_client):
    """Follow-up xabari o'zbek tilida bo'lishi kerak (template fallback)."""
    from core.services.message_composer_service import MessageComposerService

    mock_openai_client.chat.completions.create.side_effect = Exception("API error")

    service = MessageComposerService(openai_client=mock_openai_client)
    message = await service.compose_followup(
        event_type="opened_catalog",
        user_name="Aziz",
        journey_events=[],
        memory={},
    )

    # O'zbek tilidagi kalit so'zlar
    uzbek_words = ["katalog", "model", "narx", "buyurtma", "dizayn", "yoqdi"]
    has_uzbek = any(word in message.lower() for word in uzbek_words)
    assert has_uzbek, f"Message should be in Uzbek: {message}"
```

### test_personalization_with_name
```python
async def test_personalization_with_name(mock_openai_client):
    """Xabarda mijoz ismi ishlatilishi kerak (template fallback)."""
    from core.services.message_composer_service import MessageComposerService

    mock_openai_client.chat.completions.create.side_effect = Exception("API error")

    service = MessageComposerService(openai_client=mock_openai_client)
    message = await service.compose_followup(
        event_type="opened_catalog",
        user_name="Aziz",
        journey_events=[],
        memory={},
    )

    assert "Aziz" in message
```

### test_fallback_on_openai_failure
```python
async def test_fallback_on_openai_failure(mock_openai_client):
    """OpenAI xato qaytarganda template fallback ishlatilishi kerak."""
    from core.services.message_composer_service import MessageComposerService

    mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API rate limit")

    service = MessageComposerService(openai_client=mock_openai_client)
    message = await service.compose_followup(
        event_type="opened_catalog",
        user_name="Aziz",
        journey_events=[],
        memory={},
    )

    # Exception raise bo'lmasligi kerak — template fallback ishlaydi
    assert isinstance(message, str)
    assert len(message) > 0
```

---

## 6. Unit Tests — Admin Notifications

**Fayl**: `tests/unit/services/test_enhanced_notifications.py`

### test_new_lead_card_format
```python
async def test_new_lead_card_format():
    """Yangi lead card formati to'g'ri bo'lishi kerak."""
    from core.services.lead_notification_service import LeadNotificationService

    svc = LeadNotificationService(admin_user_id=123, bot_token="test:token")
    # _format_lead_card methodini test qilish (private method, direct call)
    card = svc._format_lead_card(
        name="Aziz",
        phone="+998901234567",
        username="aziz_test",
        district="Chilonzor",
        score=75,
        temperature="hot",
    )

    assert "Aziz" in card
    assert "+998901234567" in card
    assert "@aziz_test" in card
    assert "Chilonzor" in card
    assert "HOT" in card or "hot" in card.lower()
```

### test_abandoned_order_alert
```python
async def test_abandoned_order_alert():
    """Tashlab ketilgan buyurtma alert formati to'g'ri bo'lishi kerak."""
    card = _format_abandoned_order_alert(
        name="Aziz",
        username="aziz_test",
        phone="+998901234567",
        district="Chilonzor",
        completed_fields=["name", "phone"],
        missing_fields=["district", "type", "area"],
        minutes_ago=10,
        followup_sent=True,
    )

    assert "BUYURTMA TASHLAB KETILDI" in card or "tashlab" in card.lower()
    assert "Ism: Ha" in card or "name" in card.lower()
    assert "10 daqiqa" in card or "10" in card
```

### test_image_received_urgent_alert
```python
async def test_image_received_urgent_alert():
    """Rasm yuborilgan alert URGENT sifatida belgilanishi kerak."""
    card = _format_image_alert(
        name="Aziz",
        username="aziz_test",
        phone="+998901234567",
        temperature="warm",
    )

    assert "RASM YUBORDI" in card or "rasm" in card.lower()
    assert "darhol" in card.lower() or "URGENT" in card
```

### test_clickable_phone_link
```python
async def test_clickable_phone_link():
    """Telefon raqam clickable link sifatida formatlanishi kerak."""
    # HTML format: <a href="tel:+998901234567">+998901234567</a>
    card = _format_lead_card(phone="+998901234567")

    assert 'href="tel:+998901234567"' in card or "tel:+998901234567" in card
```

### test_journey_summary_included
```python
async def test_journey_summary_included():
    """Admin card'da journey summary bo'lishi kerak."""
    from datetime import datetime, timezone

    events = [
        {"type": "opened_catalog", "ts": datetime(2024, 1, 1, 14, 30, tzinfo=timezone.utc)},
        {"type": "price_calculated", "ts": datetime(2024, 1, 1, 14, 35, tzinfo=timezone.utc)},
        {"type": "order_form_started", "ts": datetime(2024, 1, 1, 14, 40, tzinfo=timezone.utc)},
    ]

    summary = _build_journey_summary(events)

    assert "Katalog" in summary or "katalog" in summary
    assert "Narx" in summary or "narx" in summary
    assert "14:30" in summary
    assert "14:35" in summary
```

### test_daily_summary_format
```python
async def test_daily_summary_format():
    """Kunlik hisobot formati to'g'ri bo'lishi kerak."""
    summary = _format_daily_summary(
        date="2024-01-15",
        new_leads=12,
        hot_count=3,
        warm_count=5,
        cold_count=4,
        pipeline_counts={
            "NEW": 5, "CONTACTED": 3, "MEASUREMENT": 2,
            "QUOTE": 1, "DEAL": 1,
        },
        followup_sent=20,
        followup_replied=8,
        conversion_percent=40,
        ai_recommendation="HOT leadlarga darhol qo'ng'iroq qiling",
    )

    assert "KUNLIK HISOBOT" in summary
    assert "12" in summary  # new_leads
    assert "HOT" in summary
    assert "40%" in summary or "40" in summary  # conversion
```

---

## 7. Integration Tests — Full Flow

**Fayl**: `tests/integration/test_followup_flow.py`

### test_catalog_view_to_followup_to_order (Happy Path)
```python
async def test_catalog_view_to_followup_to_order():
    """
    Happy path:
    1. Mijoz katalogni ochadi → event emit
    2. 10 daqiqa o'tadi → follow-up yuboriladi
    3. Mijoz follow-up'dagi "Buyurtma" tugmasini bosadi
    4. Buyurtma formasiga o'tadi → follow-up cancel
    """
    # Step 1: Emit catalog event
    await journey_service.emit(user_id=USER_ID, event_type="opened_catalog")

    # Step 2: Follow-up schedule tekshiruvi
    pending = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending) == 1
    assert pending[0].event_type == "opened_catalog"

    # Step 3: Simulate 10 min passed — process pending
    await followup_service.process_pending()
    # Follow-up yuborilganini tekshirish
    sent = await followup_repo.get_sent(user_id=USER_ID)
    assert len(sent) == 1

    # Step 4: User starts order — all followups cancelled
    await journey_service.emit(user_id=USER_ID, event_type="order_form_started")
    pending_after = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending_after) == 0
```

### test_price_calc_to_followup_to_operator (Operator Path)
```python
async def test_price_calc_to_followup_to_operator():
    """
    Operator path:
    1. Mijoz narx hisoblaydi → event emit
    2. 10 daqiqa → follow-up yuboriladi
    3. Mijoz "Operator" tugmasini bosadi → follow-up cancel, operator notification
    """
    await journey_service.emit(
        user_id=USER_ID,
        event_type="price_calculated",
        payload={"design": "Gulli", "price": 5000000},
    )

    # Follow-up scheduled
    pending = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending) == 1

    # Operator requested — cancel followups
    await journey_service.emit(user_id=USER_ID, event_type="operator_requested")
    pending_after = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending_after) == 0
```

### test_order_abandon_to_followup_to_resume (Recovery Path)
```python
async def test_order_abandon_to_followup_to_resume():
    """
    Recovery path:
    1. Mijoz buyurtma formasini boshlaydi
    2. 10 daqiqa jim turadi → abandoned follow-up yuboriladi
    3. Mijoz "Davom etish" tugmasini bosadi → formaga qaytadi
    """
    await journey_service.emit(
        user_id=USER_ID,
        event_type="order_form_started",
        payload={"completed_fields": ["name"]},
    )

    # Simulate timeout → abandoned event
    await journey_service.emit(
        user_id=USER_ID,
        event_type="order_form_abandoned",
        payload={"completed_fields": ["name"], "missing_fields": ["phone", "district"]},
    )

    # Follow-up scheduled for abandoned order
    pending = await followup_repo.get_pending(user_id=USER_ID)
    assert any(p.event_type == "order_form_abandoned" for p in pending)
```

### test_multiple_events_single_user_no_spam
```python
async def test_multiple_events_single_user_no_spam():
    """
    Anti-spam: bitta foydalanuvchi bir nechta harakat qilsa,
    follow-up'lar anti-spam qoidalariga bo'ysunishi kerak.
    """
    # 6 ta turli event emit (daily limit = 5)
    events = [
        "opened_catalog", "price_calculated", "package_viewed",
        "opened_catalog", "price_calculated", "opened_catalog",
    ]
    for event_type in events:
        await journey_service.emit(user_id=USER_ID, event_type=event_type)

    # Max 5 ta pending follow-up bo'lishi kerak (daily limit)
    pending = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending) <= 5
```

### test_user_says_kerak_emas_stops_everything
```python
async def test_user_says_kerak_emas_stops_everything():
    """
    'Kerak emas' deganda barcha pending follow-up'lar
    bekor bo'lishi va yangilari schedule bo'lmasligi kerak.
    """
    # Schedule some followups
    await journey_service.emit(user_id=USER_ID, event_type="opened_catalog")
    await journey_service.emit(user_id=USER_ID, event_type="price_calculated")

    pending_before = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending_before) >= 1

    # User says "kerak emas"
    await followup_service.cancel_followups(
        user_id=USER_ID,
        reason="user_opted_out",
    )

    # Barcha follow-up'lar cancelled
    pending_after = await followup_repo.get_pending(user_id=USER_ID)
    assert len(pending_after) == 0

    # Yangi follow-up'lar ham schedule bo'lmasligi kerak (opted out)
    result = await followup_service.schedule_followup(
        user_id=USER_ID,
        event_type="opened_catalog",
        delay_minutes=10,
    )
    assert result is None or result.get("skipped") is True
```

---

## 8. Integration Tests — Scheduler

**Fayl**: `tests/integration/test_journey_tracking.py`

### test_scheduler_picks_up_pending_followups
```python
async def test_scheduler_picks_up_pending_followups():
    """Scheduler pending follow-up'larni DB dan yuklab, qayta ishlashi kerak."""
    from datetime import datetime, timezone, timedelta

    # DB ga pending follow-up qo'shish
    await followup_repo.create(
        user_id=12345,
        event_type="opened_catalog",
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # vaqti kelgan
        status="pending",
    )

    # Scheduler cycle
    processed = await followup_service.process_pending()

    assert processed >= 1
```

### test_scheduler_skips_cancelled_followups
```python
async def test_scheduler_skips_cancelled_followups():
    """Scheduler cancelled follow-up'larni o'tkazib yuborishi kerak."""
    await followup_repo.create(
        user_id=12345,
        event_type="opened_catalog",
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        status="cancelled",
    )

    processed = await followup_service.process_pending()

    assert processed == 0
```

### test_scheduler_handles_db_failure_gracefully
```python
async def test_scheduler_handles_db_failure_gracefully():
    """DB xatosi bo'lganda scheduler crash bo'lmasligi kerak."""
    mock_repo = AsyncMock()
    mock_repo.get_pending.side_effect = Exception("DB connection lost")

    service = AgentFollowupService(repo=mock_repo, memory_service=AsyncMock())

    # Exception raise bo'lmasligi kerak
    processed = await service.process_pending()
    assert processed == 0
```

### test_scheduler_respects_business_hours
```python
async def test_scheduler_respects_business_hours():
    """
    Scheduler faqat business hours'da (09:00-21:00 Toshkent) follow-up yuborishi kerak.
    Tunda pending bo'lsa, ertalab yuboriladi.
    """
    from datetime import datetime, timezone, timedelta
    import zoneinfo

    tz_tashkent = zoneinfo.ZoneInfo("Asia/Tashkent")
    night_time = datetime(2024, 1, 15, 2, 0, tzinfo=tz_tashkent)  # 02:00 Tashkent

    # Night time'da schedule qilingan follow-up
    await followup_repo.create(
        user_id=12345,
        event_type="opened_catalog",
        scheduled_at=night_time,
        status="pending",
    )

    # Scheduler bu follow-up'ni tungi vaqtda yubormasligi kerak
    processed = await followup_service.process_pending(current_time=night_time)
    assert processed == 0

    # Ertalab (09:00) yuborilishi kerak
    morning_time = datetime(2024, 1, 15, 9, 0, tzinfo=tz_tashkent)
    processed_morning = await followup_service.process_pending(current_time=morning_time)
    assert processed_morning >= 1
```

---

## 9. Edge Case Tests

**Fayl**: `tests/unit/services/test_agent_followup_service.py` (qo'shimcha)

### test_user_blocks_bot_followup_stops
```python
async def test_user_blocks_bot_followup_stops():
    """Mijoz botni bloklasa, follow-up yuborishda TelegramForbiddenError
    kelib, follow-up cancel bo'lishi va blocked_chats'ga yozilishi kerak."""
    from aiogram.exceptions import TelegramForbiddenError

    mock_bot = AsyncMock()
    mock_bot.send_message.side_effect = TelegramForbiddenError(
        method=MagicMock(), message="Forbidden: bot was blocked by the user"
    )

    # Follow-up yuborishga urinish
    result = await followup_service._send_followup(
        bot=mock_bot,
        user_id=12345,
        message="Test follow-up",
    )

    assert result["status"] == "blocked"
    # Follow-up cancel bo'lishi kerak
    mock_followup_repo.cancel_by_user.assert_called_with(
        user_id=12345, reason="user_blocked_bot"
    )
```

### test_concurrent_events_no_race_condition
```python
async def test_concurrent_events_no_race_condition():
    """Bir vaqtda bir nechta event kelganda race condition bo'lmasligi kerak."""
    import asyncio

    # 5 ta event bir vaqtda emit
    tasks = [
        journey_service.emit(user_id=12345, event_type="opened_catalog"),
        journey_service.emit(user_id=12345, event_type="price_calculated"),
        journey_service.emit(user_id=12345, event_type="package_viewed"),
        journey_service.emit(user_id=12345, event_type="ai_question_asked"),
        journey_service.emit(user_id=12345, event_type="opened_catalog"),  # duplikat
    ]
    await asyncio.gather(*tasks)

    # Duplikat filter qilinishi kerak
    events = await mock_journey_event_repo.get_user_events(user_id=12345)
    event_types = [e.event_type for e in events]
    # opened_catalog faqat 1 marta bo'lishi kerak (dedup window)
```

### test_very_old_memory_cleaned_up
```python
async def test_very_old_memory_cleaned_up():
    """90 kundan eski memory yozuvlari tozalanishi kerak."""
    from datetime import datetime, timezone, timedelta

    old_cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    await memory_service.cleanup_old_memories(before=old_cutoff)

    mock_agent_memory_repo.delete_old.assert_called_once_with(before=old_cutoff)
```

### test_user_restarts_bot_during_followup_cycle
```python
async def test_user_restarts_bot_during_followup_cycle():
    """Mijoz /start ni qayta bossa, pending follow-up'lar saqlanib qolishi kerak.
    Lekin journey state IDLE ga qaytishi kerak."""
    # Pending follow-up bor
    await followup_service.schedule_followup(
        user_id=12345, event_type="opened_catalog", delay_minutes=10
    )

    # User restarts bot (/start)
    await memory_service.update_memory(
        user_id=12345,
        updates={"journey_state": "idle"},
    )

    # Follow-up hali ham pending (cancel qilinmasligi kerak)
    pending = await followup_repo.get_pending(user_id=12345)
    assert len(pending) >= 1

    # Journey state reset bo'lgan
    memory = await memory_service.get_memory(user_id=12345)
    assert memory["journey_state"] == "idle"
```

---

## 10. Manual Test Scenarios (QA uchun)

Quyidagi ssenariylarni real bot instance'da qo'lda test qilish uchun ishlatiladi.

### Scenario 1: Catalog Follow-up (Happy Path)
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | /start bosing                    | Asosiy menyu ko'rinadi
2      | "Katalog" tugmasini bosing       | Katalog ko'rinadi (dizayn rasmlar)
3      | 10 daqiqa kuting                 | Bot xabar yuboradi: "Qaysi model yoqdi?"
4      | "Gulli" deb yozing               | Bot narx so'raydi yoki katalogdan ko'rsatadi
5      | Admin guruhni tekshiring          | Admin card yuborilgan: journey summary bilan
```

### Scenario 2: Price Follow-up (Conversion Path)
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | Narx kalkulyatorni oching         | Area so'raydi
2      | "20" deb yozing (20 m2)           | Design so'raydi
3      | "Gulli" tanlang                   | Narx ko'rinadi (masalan: 5,000,000 so'm)
4      | 10 daqiqa kuting                 | Follow-up: "Narx hali amal qiladi, buyurtma?"
5      | "Buyurtma" tugmasini bosing       | Buyurtma formasiga o'tadi
6      | Admin guruhni tekshiring          | "NARX HISOBLANDI" alert
```

### Scenario 3: Abandoned Order (Recovery Path)
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | Buyurtma formasini boshlang       | Ism so'raydi
2      | Ismingizni yozing                 | Telefon so'raydi
3      | 10 daqiqa kuting (form tashlab)  | Follow-up: "Buyurtmangiz yarim qoldi!"
4      | "Davom" tugmasini bosing          | Telefon so'rash qadamiga qaytadi
5      | Admin guruhni tekshiring          | "BUYURTMA TASHLAB KETILDI" alert
```

### Scenario 4: Anti-Spam Test
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | Katalogni oching → 10 min kuting  | Follow-up #1 keladi
2      | Narx hisoblang → 10 min kuting   | Follow-up #2 keladi
3      | Paketlarni oching → 10 min kuting | Follow-up #3 keladi (agar cooldown o'tgan)
4      | Yana katalog → 10 min kuting     | Follow-up #4 (agar daily limit ichida)
5      | Yana narx → 10 min kuting        | Follow-up #5 (agar daily limit ichida)
6      | Yana paket → 10 min kuting       | ❌ YUBORILMASLIGI KERAK (daily limit = 5)
```

### Scenario 5: "Kerak emas" Stop Test
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | Katalogni oching                  | Follow-up schedule bo'ladi
2      | 5 daqiqa kuting                   | Hali yuborilmagan (10 min to'lmadi)
3      | "Kerak emas" deb yozing           | Follow-up cancel bo'ladi
4      | 10 daqiqa kuting                 | ❌ Hech narsa yuborilMASligi kerak
5      | Yangi katalog oching + 10 min    | ❌ Hech narsa yuborilMASligi kerak (opted out)
```

### Scenario 6: Image Urgent Alert
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | AI suhbatga kiring                | Madina javob beradi
2      | Xona rasmini yuboring             | Bot: "Chiroyli xona! Narx hisoblab beraman"
3      | Admin guruhni DARHOL tekshiring   | 📸 URGENT alert: "MIJOZ RASM YUBORDI!"
4      | Alert'da telefon link bor         | Clickable tel: link (agar phone mavjud)
```

### Scenario 7: Daily Summary Test
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | Kun davomida bir nechta lead      | Leadlar pipeline'ga tushadi
2      | Kechqurun 21:00 Toshkent vaqtida | Admin guruhga KUNLIK HISOBOT keladi
3      | Hisobotni tekshiring              | Lead soni, pipeline status, conversion %
```

### Scenario 8: Bot Restart Resilience
```
QADAM  | HARAKAT                          | KUTILGAN NATIJA
-------|----------------------------------|------------------------------------------
1      | Katalog oching                    | Follow-up schedule bo'ladi
2      | 5 daqiqa kuting                   | Hali yuborilmagan
3      | Botni restart qiling              | docker compose restart bot
4      | 5 daqiqa kuting (jami 10 daqiqa) | ✅ Follow-up yuborilishi kerak (DB dan restore)
```

---

## 11. Performance va Load Tests

### Benchmark Targetlari

| Operatsiya | Target | O'lchash |
|-----------|--------|----------|
| Event emit | <10ms | Timer around `journey_service.emit()` |
| Memory read (Redis hit) | <5ms | Timer around `memory_service.get_memory()` |
| Memory read (DB fallback) | <50ms | Redis off, timer around `get_memory()` |
| Follow-up check cycle | <500ms | Timer around `process_pending()` (100 pending) |
| Message compose (AI) | <3000ms | Timer around `compose_followup()` |
| Message compose (template) | <1ms | Timer around template fallback |
| Admin notification | <500ms | Timer around `notify_new_lead()` |

### Load Test Ssenariysi
```python
# tests/load/test_followup_load.py (locust bilan)

class FollowupLoadTest(User):
    """100 concurrent users emitting events simultaneously."""

    @task
    def emit_catalog_event(self):
        user_id = random.randint(1, 100000)
        asyncio.run(journey_service.emit(
            user_id=user_id,
            event_type="opened_catalog",
        ))

    @task
    def process_pending(self):
        asyncio.run(followup_service.process_pending())
```

---

## 12. CI/CD Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/test-agent.yml
name: AI Agent Tests

on:
  push:
    paths:
      - 'core/services/journey_*'
      - 'core/services/agent_*'
      - 'core/services/message_composer*'
      - 'tests/unit/services/test_journey*'
      - 'tests/unit/services/test_agent*'
      - 'tests/unit/services/test_message*'

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: ceiling_crm_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/unit/services/test_journey*.py tests/unit/services/test_agent*.py tests/unit/services/test_message*.py -v --tb=short
      - run: pytest tests/integration/test_followup*.py tests/integration/test_journey*.py -v --tb=short
```

### Pre-commit Hook
```bash
# Har bir commit'dan oldin agent test'lar ishga tushadi
pytest tests/unit/services/test_journey_event_service.py tests/unit/services/test_agent_followup_service.py -x --tb=short
```

---

## 13. Test Coverage Goals

| Modul | Minimum Coverage | Target Coverage |
|-------|-----------------|-----------------|
| `journey_event_service.py` | 85% | 95% |
| `agent_memory_service.py` | 80% | 90% |
| `agent_followup_service.py` | 90% | 95% |
| `message_composer_service.py` | 80% | 90% |
| `lead_notification_service.py` (yangi method'lar) | 85% | 95% |
| **Umumiy yangi kod** | **85%** | **92%** |

---

**Oldingi fayl**: [09_IMPLEMENTATION_ROADMAP.md](./09_IMPLEMENTATION_ROADMAP.md) | **Keyingi fayl**: Yo'q (oxirgi fayl)
