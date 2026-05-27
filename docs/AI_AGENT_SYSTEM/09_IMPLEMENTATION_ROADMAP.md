# 09 — Implementation Roadmap (Amalga Oshirish Yo'l Xaritasi)

## Umumiy Ko'rinish

AI Agent System'ni bosqichma-bosqich joriy etish rejasi. Har bir qadam mustaqil deploy qilinishi mumkin va oldingi qadamlar to'liq ishlayotganiga bog'liq.

### Qoidalar
1. **Additive only** — mavjud funksionallikni buzmang, faqat yangi qo'shing
2. **Har bir qadam testlanadi** — deploy'dan oldin unit + integration test'lar pass bo'lishi shart
3. **Rollback tayyor** — har bir qadam uchun rollback rejasi bor
4. **Feature flag** — yangi funksional Redis/env orqali o'chirib qo'yilishi mumkin

### Taxminiy Jami Vaqt: 8-12 ish kuni

```
STEP A ──► STEP B ──► STEP C ──► STEP D ──► STEP E ──► STEP F
 (docs)    (events)  (memory)   (scheduler)  (catalog)  (price)
  0.5d      2d        1.5d       2d           1d         1d
                                    │
                                    ├──► STEP G ──► STEP H ──► STEP I ──► STEP J
                                    │    (abandon)  (admin)    (AI msg)   (tests)
                                    │     1.5d       1d         1.5d       1.5d
                                    │
                                    └──► STEP E, F, G parallel mumkin
```

---

## STEP A — Documentation (HOZIRGI QADAM)

### Maqsad
AI Agent System uchun to'liq texnik dokumentatsiya yaratish. Arxitektura, flow'lar, test rejasi va roadmap.

### O'zgartiriladigan Fayllar
- Yangi fayllar shu katalogda

### Yangi Fayllar
| Fayl | Vazifa |
|------|--------|
| `docs/AI_AGENT_SYSTEM/08_ADMIN_NOTIFICATIONS.md` | Admin xabarnomalar formatlari |
| `docs/AI_AGENT_SYSTEM/09_IMPLEMENTATION_ROADMAP.md` | Amalga oshirish yo'l xaritasi (shu fayl) |
| `docs/AI_AGENT_SYSTEM/10_TEST_PLAN.md` | Test rejasi va test ssenariylari |

### Test Qilish Usuli
- Docs review — to'g'rilik va to'liqlik tekshiruvi
- Fayl yo'llari va klass nomlari haqiqiy kodga mos kelishini tekshirish

### Risk: None
Faqat dokumentatsiya — kodga ta'sir yo'q.

### Rollback Plan
```bash
rm -rf docs/AI_AGENT_SYSTEM/08_*.md docs/AI_AGENT_SYSTEM/09_*.md docs/AI_AGENT_SYSTEM/10_*.md
```

### Dependencies: Yo'q (birinchi qadam)
### Taxminiy Vaqt: 0.5 ish kuni

---

## STEP B — Event Tracking Foundation (Journey Event Collection)

### Maqsad
Mijozning har bir muhim harakatini (event) qayd qilib, journey state machine'ni boshqarish uchun infratuzilma qurish.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `shared/constants/enums.py` | `JourneyEventType` enum qo'shish (OPENED_CATALOG, PRICE_CALCULATED, ORDER_FORM_STARTED, ORDER_FORM_ABANDONED, AI_QUESTION_ASKED, OPERATOR_REQUESTED, PHONE_SHARED, PACKAGE_VIEWED, IMAGE_SENT, ORDER_COMPLETED) |
| `apps/bot/handlers/private/catalog.py` | `emit(OPENED_CATALOG)` handler boshida |
| `apps/bot/handlers/private/ai_support.py` | `emit(AI_QUESTION_ASKED)` va `emit(IMAGE_SENT)` |
| `apps/bot/handlers/private/lead_capture.py` | `emit(PHONE_SHARED)` telefon qabul qilinganda |
| `apps/bot/handlers/private/packages.py` | `emit(PACKAGE_VIEWED)` paket ko'rilganda |
| `apps/bot/handlers/private/operator.py` | `emit(OPERATOR_REQUESTED)` operator so'ralganda |
| `infrastructure/di.py` | `get_journey_event_service(session)` factory qo'shish |

### Yangi Fayllar

| Fayl | Vazifa |
|------|--------|
| `shared/constants/journey.py` | `JourneyEventType` enum va `JourneyState` state machine constants |
| `core/services/journey_event_service.py` | Event emit + journey state update logic |
| `core/repositories/journey_event_repo.py` | Abstract repository: `create_event()`, `get_user_events()`, `get_latest_state()` |
| `infrastructure/database/repositories/journey_event_repo.py` | PostgreSQL implementation |
| `infrastructure/database/models/journey_event.py` | `JourneyEventModel` — id, user_id, event_type, payload JSON, created_at, journey_state |
| `infrastructure/database/migrations/versions/xxx_add_journey_events.py` | Alembic migration: `journey_events` jadval |

### Texnik Tafsilotlar

**JourneyEventType enum**:
```python
class JourneyEventType(str, Enum):
    OPENED_CATALOG       = "opened_catalog"
    PRICE_CALCULATED     = "price_calculated"
    ORDER_FORM_STARTED   = "order_form_started"
    ORDER_FORM_ABANDONED = "order_form_abandoned"
    ORDER_COMPLETED      = "order_completed"
    AI_QUESTION_ASKED    = "ai_question_asked"
    OPERATOR_REQUESTED   = "operator_requested"
    PHONE_SHARED         = "phone_shared"
    PACKAGE_VIEWED       = "package_viewed"
    IMAGE_SENT           = "image_sent"
```

**Journey State Machine**:
```
IDLE ──► BROWSING ──► CALCULATING ──► ORDERING ──► CONTACTED ──► CONVERTED
  │          │             │              │             │              │
  └──────────┴─────────────┴──────────────┴─────────────┴── LOST ◄────┘
```

**Handler'larga Event Emit Qo'shish Namunasi**:
```python
# catalog.py — katalog ochilganda
from core.services.journey_event_service import JourneyEventService

async def handle_catalog(message: Message, db_session: AsyncSession, **data):
    # Mavjud kod...
    # Event emit (fire-and-forget)
    svc = get_journey_event_service(db_session)
    await svc.emit(user_id=message.from_user.id, event_type=JourneyEventType.OPENED_CATALOG)
```

### Test Qilish Usuli
```bash
# Unit test'lar
pytest tests/unit/services/test_journey_event_service.py -v

# Tekshirish: har bir handler harakat bo'lganda event emit qiladi
# Tekshirish: journey state to'g'ri yangilanadi
# Tekshirish: duplikat event'lar filtirlanadi (dedup window)
```

### Risk: LOW
- Faqat additive o'zgarishlar — mavjud handler'larga 2-3 qator qo'shiladi
- Event emit `try/except` bilan o'raladi — xato bo'lsa asosiy flow'ga ta'sir qilmaydi
- Yangi jadval — mavjud jadvallar o'zgarmaydi

### Rollback Plan
```bash
# Migration revert
alembic downgrade -1

# Yangi fayllar o'chirish
rm core/services/journey_event_service.py
rm core/repositories/journey_event_repo.py
rm infrastructure/database/repositories/journey_event_repo.py
rm infrastructure/database/models/journey_event.py

# Handler'lardagi emit qatorlarini o'chirish (git revert)
git checkout -- apps/bot/handlers/private/catalog.py
git checkout -- apps/bot/handlers/private/ai_support.py
# ... boshqa handler'lar
```

### Dependencies: STEP A (docs)
### Taxminiy Vaqt: 2 ish kuni

---

## STEP C — Agent Memory Table (Structured Per-User Memory)

### Maqsad
Har bir foydalanuvchi uchun structured memory: journey state, intent history, follow-up history. Redis (tez access) + PostgreSQL (persistent backup).

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `infrastructure/cache/keys.py` | `AGENT_MEMORY` key prefix va TTL qo'shish: `agent:memory:{user_id}` (30 kun), `agent:state:{user_id}` (7 kun) |
| `infrastructure/di.py` | `get_agent_memory_service(session)` factory qo'shish |

### Yangi Fayllar

| Fayl | Vazifa |
|------|--------|
| `core/services/agent_memory_service.py` | Memory CRUD: `get_memory()`, `update_memory()`, `clear_memory()`, `sync_to_db()` |
| `core/repositories/agent_memory_repo.py` | Abstract: `upsert_state()`, `get_state()`, `list_stale()`, `delete_old()` |
| `infrastructure/database/repositories/agent_memory_repo.py` | PostgreSQL implementation with `ON CONFLICT DO UPDATE` |
| `infrastructure/database/models/agent_state.py` | `AgentStateModel` — user_id (PK), journey_state, last_event_type, intent_history (JSONB), follow_up_history (JSONB), updated_at, created_at |
| `infrastructure/database/migrations/versions/xxx_add_agent_state.py` | Alembic migration |

### Texnik Tafsilotlar

**AgentStateModel**:
```python
class AgentStateModel(Base):
    __tablename__ = "agent_states"

    user_id         = sa.Column(sa.BigInteger, primary_key=True)
    journey_state   = sa.Column(sa.String(32), default="idle")
    last_event_type = sa.Column(sa.String(64), nullable=True)
    intent_history  = sa.Column(JSONB, default=list)     # [{type, ts, payload}]
    follow_up_history = sa.Column(JSONB, default=list)   # [{type, ts, result}]
    updated_at      = sa.Column(sa.DateTime(timezone=True), onupdate=func.now())
    created_at      = sa.Column(sa.DateTime(timezone=True), server_default=func.now())
```

**Redis + DB Sync Strategy**:
1. Read: Redis first, DB fallback (cache-aside)
2. Write: Redis immediate, DB async (write-behind)
3. Cleanup: 90 kundan eski DB yozuvlar cron job bilan o'chiriladi
4. Crash recovery: Bot restart'da Redis bo'sh bo'lsa, DB dan yuklaydi

**MUHIM**: Telefon raqami agent memory'da saqlanMAYDI — faqat `leads` jadvalida.

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_agent_memory_service.py -v

# Memory CRUD operatsiyalar
# Redis-DB sync
# 90 kunlik cleanup
# Crash recovery scenario
```

### Risk: LOW
- Yangi jadval — mavjud tizimga ta'sir yo'q
- Redis key'lar namespace'i ajratilgan (`agent:` prefix)
- Mavjud `ai:memory:` key'lar bilan conflict yo'q

### Rollback Plan
```bash
alembic downgrade -1
rm core/services/agent_memory_service.py
rm core/repositories/agent_memory_repo.py
rm infrastructure/database/repositories/agent_memory_repo.py
rm infrastructure/database/models/agent_state.py
# Redis key'lar TTL bilan o'zi o'chadi
```

### Dependencies: STEP B (event tracking)
### Taxminiy Vaqt: 1.5 ish kuni

---

## STEP D — 10-Minute Follow-up Scheduler

### Maqsad
Event-driven follow-up scheduling engine: hodisa sodir bo'lganda 10 daqiqalik taymer boshlaydi, vaqt kelganda to'g'ri xabarni yuboradi.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `apps/scheduler/main.py` | `check_agent_followups` job'ni ro'yxatga olish (60s interval, mavjud `check_due_followups` ga o'xshash) |
| `infrastructure/cache/keys.py` | Follow-up dedup key'lari: `agent:fu:pending:{user_id}:{event_type}` (10 min TTL), `agent:fu:daily_count:{user_id}` (24 soat TTL), `agent:fu:hourly_count:{user_id}` (1 soat TTL) |

### Yangi Fayllar

| Fayl | Vazifa |
|------|--------|
| `core/services/agent_followup_service.py` | Follow-up qoidalar engine: `schedule_followup()`, `cancel_followups()`, `process_pending()`, `check_anti_spam()` |
| `apps/scheduler/jobs/agent_followup_jobs.py` | APScheduler job: `check_agent_followups()` — har 60s pending follow-up'larni tekshiradi |
| `infrastructure/database/models/scheduled_followup.py` | `ScheduledFollowupModel` — id, user_id, event_type, scheduled_at, status (pending/sent/cancelled), payload JSON, created_at |
| `infrastructure/database/migrations/versions/xxx_add_scheduled_followups.py` | Alembic migration + index on `(status, scheduled_at)` |

### Texnik Tafsilotlar

**Follow-up Qoidalari**:
```python
FOLLOWUP_RULES = {
    "opened_catalog":       {"delay_min": 10, "max_per_type": 1, "priority": 3},
    "price_calculated":     {"delay_min": 10, "max_per_type": 1, "priority": 2},
    "order_form_abandoned": {"delay_min": 10, "max_per_type": 1, "priority": 1},
    "package_viewed":       {"delay_min": 15, "max_per_type": 1, "priority": 4},
    "image_sent":           {"delay_min": 5,  "max_per_type": 1, "priority": 1},
}
```

**Anti-Spam Qoidalari**:
```python
MAX_FOLLOWUPS_PER_DAY  = 5   # per user per day
MAX_FOLLOWUPS_PER_HOUR = 2   # per user per hour
COOLDOWN_BETWEEN_MIN   = 15  # min daqiqa between any two follow-ups
```

**Cancel Conditions** (follow-up bekor bo'ladi agar):
1. Mijoz javob yozsa (any message)
2. Mijoz buyurtma bersa (ORDER_COMPLETED)
3. Mijoz operator so'rasa (OPERATOR_REQUESTED)
4. Mijoz "kerak emas" / "stop" desa
5. Admin lead'ni CONTACTED yoki DEAL ga o'tkazsa

**Scheduler Flow**:
```
Event sodir bo'ldi
  └── agent_followup_service.schedule_followup(user_id, event_type, delay=10min)
      └── Anti-spam tekshiruvi (daily/hourly limit)
      └── Dedup tekshiruvi (same event type pending?)
      └── scheduled_followups jadvaliga yozish (status=pending)
      └── Redis dedup key set (NX, 10min TTL)

60 soniyada scheduler:
  └── check_agent_followups()
      └── SELECT * FROM scheduled_followups WHERE status='pending' AND scheduled_at <= NOW()
      └── Har bir pending follow-up uchun:
          ├── Cancel condition tekshiruvi
          ├── Business hours tekshiruvi (09:00-21:00 Toshkent)
          ├── Message compose (STEP I ga qadar template, keyin AI)
          └── Bot.send_message(user_id, message, reply_markup=keyboard)
          └── status = 'sent', sent_at = NOW()
```

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_agent_followup_service.py -v
pytest tests/integration/test_followup_scheduler.py -v

# Unit: schedule created, cancelled, processed
# Unit: anti-spam limits respected
# Unit: dedup works
# Integration: end-to-end with scheduler
```

### Risk: MEDIUM
- **Timing-sensitive** — follow-up aniq vaqtda yuborilishi kerak
- **Anti-spam** — noto'g'ri sozlash spam'ga olib kelishi mumkin
- **Bot restart** — pending follow-up'lar DB'da saqlanadi, restart'dan keyin davom etadi
- **Race condition** — bir vaqtda bir nechta scheduler instance ishlashi mumkin (Redis lock bilan hal qilish)

### Mitigatsiya
- Redis distributed lock: `agent:scheduler:lock` (60s TTL) — faqat bitta scheduler instance ishlaydi
- Idempotent processing: follow-up status'ini `sent` ga o'zgartirish atomic (WHERE status='pending')
- Graceful degradation: scheduler ishlamasa, follow-up'lar shunchaki kechikadi (yo'qolmaydi)

### Rollback Plan
```bash
# Scheduler job'ni o'chirish (apps/scheduler/main.py dan olib tashlash)
# yoki feature flag bilan disable:
# AGENT_FOLLOWUP_ENABLED=false

alembic downgrade -1
rm core/services/agent_followup_service.py
rm apps/scheduler/jobs/agent_followup_jobs.py
rm infrastructure/database/models/scheduled_followup.py
```

### Dependencies: STEP B (events) + STEP C (memory)
### Taxminiy Vaqt: 2 ish kuni

---

## STEP E — Catalog Follow-up

### Maqsad
Mijoz katalogni ochib, 10 daqiqa hech narsa qilmasa — agent "Qaysi model yoqdi?" deb so'raydi.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `core/services/agent_followup_service.py` | `_compose_catalog_followup()` method qo'shish |
| `apps/bot/handlers/private/catalog.py` | `schedule_followup(OPENED_CATALOG)` emit qo'shish |

### Yangi Fayllar
Yo'q — STEP D da yaratilgan infratuzilmani ishlatadi.

### Texnik Tafsilotlar

**Follow-up Xabari**:
```
Assalomu alaykum, {name}! 😊

Katalogimizda qaysi model ko'zingizga tushdi?
Kvadrat metringizni yozsangiz, aniq narxini hisoblab beraman!

[💰 Narx hisoblash] [📞 Operator] [❌ Kerak emas]
```

**Cancel Conditions**:
- Mijoz narx kalkulyator ishlatsa (PRICE_CALCULATED)
- Mijoz buyurtma boshlasa (ORDER_FORM_STARTED)
- Mijoz boshqa xabar yozsa (any message within 10 min)

**Flow**:
```
Mijoz katalogni ochadi
  └── catalog.py: schedule_followup(user_id, OPENED_CATALOG, delay=10min)
      └── 10 daqiqa kutish
          ├── Agar mijoz boshqa harakat qilsa → cancel
          └── Agar 10 daqiqa jim tursa → follow-up yuborish
              └── "Qaysi model yoqdi?" + 3 ta button
```

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_catalog_followup.py -v

# test_catalog_followup_scheduled_on_view
# test_catalog_followup_cancelled_on_price_calc
# test_catalog_followup_cancelled_on_order
# test_catalog_followup_cancelled_on_user_message
# test_catalog_followup_message_format
# test_catalog_followup_has_correct_buttons
```

### Risk: LOW
- Faqat bitta trigger, bitta xabar
- Cancel condition'lar aniq

### Rollback Plan
```python
# agent_followup_service.py da catalog rule'ni disable:
FOLLOWUP_RULES["opened_catalog"]["enabled"] = False
```

### Dependencies: STEP D (scheduler)
### Taxminiy Vaqt: 1 ish kuni

---

## STEP F — Price Follow-up

### Maqsad
Mijoz narx hisoblab, buyurtma bermasa — 10 daqiqada eslatma + CTA yuborish.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `core/services/agent_followup_service.py` | `_compose_price_followup()` method qo'shish |
| `apps/bot/handlers/private/ai_support.py` yoki tegishli pricing handler | `schedule_followup(PRICE_CALCULATED)` emit |

### Yangi Fayllar
Yo'q — STEP D infratuzilmasini ishlatadi.

### Texnik Tafsilotlar

**Follow-up Xabari**:
```
{name}, siz {design} potolok uchun {area}m² narxini hisoblagan edingiz:

💰 {price} so'm

Bu narx bugunlik amal qiladi! Buyurtma berasizmi? 😊

[🛒 Buyurtma berish] [📞 Operator] [❌ Kerak emas]
```

**Narx Konteksti**:
- `area_m2`, `design`, `price` — FSM state dan yoki `leads` jadvalidan
- Agar lead mavjud bo'lsa — lead jadvalidan, aks holda FSM state dan

**Cancel Conditions**:
- Mijoz buyurtma boshlasa
- Mijoz operator so'rasa
- Mijoz boshqa narx hisoblasa (yangi follow-up schedule bo'ladi)

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_price_followup.py -v

# test_price_followup_includes_calculated_price
# test_price_followup_includes_design_name
# test_price_followup_cancelled_on_order
# test_price_followup_replaces_old_on_new_calc
```

### Risk: LOW
### Rollback Plan: Rule disable
### Dependencies: STEP D (scheduler)
### Taxminiy Vaqt: 1 ish kuni

---

## STEP G — Abandoned Order Follow-up

### Maqsad
Mijoz buyurtma formasini boshladi, 10 daqiqa ichida davom etmadi — agent recovery xabarini yuboradi.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `core/services/agent_followup_service.py` | `_compose_abandoned_order_followup()` method |
| `apps/bot/handlers/private/order.py` yoki tegishli FSM handler | ORDER_FORM_STARTED event emit + FSM timeout detection |

### Yangi Fayllar
Yo'q — STEP D infratuzilmasini ishlatadi.

### Texnik Tafsilotlar

**FSM Abandonment Detection**:
```python
# order.py — buyurtma formasi boshlanganda
async def handle_order_start(message, state, db_session, **data):
    # Mavjud order form logic...
    
    # Event emit
    svc = get_journey_event_service(db_session)
    await svc.emit(user_id=message.from_user.id, 
                   event_type=JourneyEventType.ORDER_FORM_STARTED,
                   payload={"started_fields": ["name"]})
    
    # Follow-up schedule (10 min timeout)
    fu_svc = get_agent_followup_service(db_session)
    await fu_svc.schedule_followup(
        user_id=message.from_user.id,
        event_type="order_form_abandoned",
        delay_minutes=10,
        payload={"completed_fields": ["name"], "missing_fields": ["phone","district","type","area"]}
    )
```

**Follow-up Xabari**:
```
{name}, buyurtmangiz yarim qoldi!

Qolgan qadamlar:
❌ Telefon raqam
❌ Tuman
❌ Potolok turi
❌ O'lcham

Davom etasizmi? 😊

[▶️ Davom etish] [📞 Operator] [❌ Bekor qilish]
```

**Qiyinchiliklar**:
- FSM state dan qaysi field'lar to'ldirilganini aniqlash
- ORDER_COMPLETED event kelsa — abandoned follow-up cancel qilish
- Mijoz boshqa handler'ga o'tsa (masalan, katalog ochsa) — cancel qilish

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_abandoned_order_followup.py -v

# test_abandoned_followup_after_10_min_silence
# test_abandoned_followup_cancelled_on_completion
# test_abandoned_followup_shows_missing_fields
# test_fsm_state_correctly_detected
# test_resume_button_returns_to_correct_fsm_step
```

### Risk: MEDIUM
- **FSM state detection** — aiogram FSM state'ini to'g'ri aniqlash murakkab
- **Cancel timing** — mijoz formasini davom ettirayotganda vaqt tugashi mumkin
- **Resume logic** — "Davom etish" tugmasi mijozni to'g'ri FSM bosqichiga qaytarishi kerak

### Mitigatsiya
- FSM state har bir step'da Redis'ga yoziladi — 10 daqiqadan keyin tekshirish mumkin
- Cancel: har bir form step'ida pending follow-up bekor qilinadi
- Resume: FSM state dan qaysi step'da to'xtagan aniqlash, o'sha step'ga qaytarish

### Rollback Plan: Rule disable
### Dependencies: STEP D (scheduler)
### Taxminiy Vaqt: 1.5 ish kuni

---

## STEP H — Admin Escalation (Enhanced Notifications)

### Maqsad
Admin xabarnomalarini journey konteksti bilan boyitish — admin nafaqat lead ma'lumotlarini, balki mijozning to'liq journey'sini ko'radi.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `core/services/lead_notification_service.py` | `notify_new_lead()` va `notify_ai_lead_collected()` methodlarini journey summary bilan kengaytirish |
| `apps/bot/handlers/private/ai_notifications.py` | Journey event'larini yig'ib, notification service'ga uzatish |

### Yangi Fayllar
Yo'q — mavjud notification tizimini kengaytirish.

### Texnik Tafsilotlar

**Journey Summary Generation**:
```python
async def _build_journey_summary(user_id: int) -> str:
    """Journey event'laridan qisqacha tarix yaratish."""
    events = await journey_event_repo.get_user_events(user_id, limit=10)
    lines = []
    for i, event in enumerate(events, 1):
        time_str = event.created_at.strftime("%H:%M")
        label = EVENT_LABELS.get(event.event_type, event.event_type)
        lines.append(f"  {i}. {label} ({time_str})")
    return "\n".join(lines)
```

**Admin Card'ga Qo'shiladigan Section**:
```
📊 Journey:
  1. Katalog ko'rdi (14:30)
  2. Narx hisobladi (14:35)
  3. Buyurtma boshladi (14:40)
  4. Form tashlab ketdi (14:50) ⚠️
```

**Yangi Notification Turlari**:
- Abandoned Order Alert (Format 2 — 08_ADMIN_NOTIFICATIONS.md)
- Price Calculated Alert (Format 3)
- Image Received Alert (Format 4)
- Follow-up No Response Alert (Format 5)

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_enhanced_notifications.py -v

# test_journey_summary_format
# test_journey_summary_max_10_events
# test_abandoned_order_alert_format
# test_image_alert_is_urgent
# test_admin_card_includes_journey
```

### Risk: LOW
- Mavjud notification service'ni kengaytirish — yangi param'lar optional
- Backward compatible — journey_summary None bo'lsa, eski format ishlatiladi

### Rollback Plan
```bash
git checkout -- core/services/lead_notification_service.py
git checkout -- apps/bot/handlers/private/ai_notifications.py
```

### Dependencies: STEP B (events) — journey event'lar kerak
### Taxminiy Vaqt: 1 ish kuni

---

## STEP I — AI Message Composer

### Maqsad
Follow-up xabarlarini kontekstga qarab OpenAI GPT-4o orqali generatsiya qilish. Template'lar o'rniga personalized xabarlar.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `apps/bot/ai/system_prompt.py` | Follow-up message composition uchun qo'shimcha prompt section |
| `core/services/agent_followup_service.py` | Template fallback'dan AI compose'ga o'tish |

### Yangi Fayllar

| Fayl | Vazifa |
|------|--------|
| `core/services/message_composer_service.py` | `compose_followup()` — context-aware message generation via OpenAI |

### Texnik Tafsilotlar

**Message Composer Service**:
```python
class MessageComposerService:
    async def compose_followup(
        self,
        *,
        event_type: str,
        user_name: str | None,
        journey_events: list[dict],
        memory: dict,
        buyer_type: str | None = None,
    ) -> str:
        """Context-aware follow-up message via OpenAI. Falls back to template on failure."""
        try:
            prompt = self._build_composition_prompt(event_type, user_name, journey_events, memory, buyer_type)
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception:
            return self._template_fallback(event_type, user_name)
```

**System Prompt** (Uzbek-specific):
```
Sen Madina — stretch potolok kompaniyasi sotuvchisi.
Vazifang: mijozga follow-up xabar yozish.
Qoidalar:
1. O'zbek tilida, samimiy va professional
2. Spam emas — foydali va qisqa
3. Mijozning harakatlariga asoslangan
4. 1-2 jumla, 1 savol, CTA button tavsiya
5. Telefon raqam so'rama — button bilan taklif qil
```

**Fallback Template'lar** (OpenAI ishlamasa):
```python
TEMPLATES = {
    "opened_catalog": "{name}, katalogdagi qaysi dizayn yoqdi? Narxini hisoblab beraman!",
    "price_calculated": "{name}, {design} uchun {price} so'm — bugun buyurtma bersangiz chegirma!",
    "order_form_abandoned": "{name}, buyurtmangiz yarim qoldi. Davom etasizmi?",
}
```

### Test Qilish Usuli
```bash
pytest tests/unit/services/test_message_composer.py -v

# test_compose_returns_uzbek_message
# test_compose_includes_user_name
# test_compose_fallback_on_openai_error
# test_compose_respects_max_length
# test_different_event_types_different_messages
# test_buyer_type_affects_tone
```

### Risk: MEDIUM
- **API cost** — har bir follow-up uchun OpenAI chaqiruv (~$0.01)
- **Latency** — OpenAI javob vaqti 1-3 soniya
- **Quality** — generatsiya qilingan xabar sifatini nazorat qilish qiyin
- **Rate limit** — OpenAI rate limit'ga tushish mumkin

### Mitigatsiya
- Template fallback — OpenAI ishlamasa, oldindan tayyor xabarlar ishlatiladi
- Caching — bir xil kontekst uchun cache'langan xabar (Redis, 1 soat TTL)
- Monitoring — xabar sifati bo'yicha admin feedback loop

### Rollback Plan
```python
# agent_followup_service.py da AI compose'ni disable:
USE_AI_COMPOSER = False  # env variable yoki settings
# Template fallback avtomatik ishga tushadi
```

### Dependencies: STEP D (scheduler) + STEP E/F/G (follow-up rules)
### Taxminiy Vaqt: 1.5 ish kuni

---

## STEP J — Tests and Production Hardening

### Maqsad
To'liq test coverage + production muhitida ishonchli ishlashni ta'minlash.

### O'zgartiriladigan Fayllar

| Fayl | O'zgarish |
|------|-----------|
| `tests/conftest.py` | Yangi mock fixture'lar qo'shish (journey_event_repo, agent_memory, followup_scheduler) |

### Yangi Fayllar

| Fayl | Vazifa |
|------|--------|
| `tests/unit/services/test_journey_event_service.py` | Journey event unit test'lar |
| `tests/unit/services/test_agent_memory_service.py` | Agent memory unit test'lar |
| `tests/unit/services/test_agent_followup_service.py` | Follow-up scheduler unit test'lar |
| `tests/unit/services/test_message_composer.py` | Message composer unit test'lar |
| `tests/unit/services/test_enhanced_notifications.py` | Admin notification unit test'lar |
| `tests/integration/test_followup_flow.py` | End-to-end follow-up integration test'lar |
| `tests/integration/test_journey_tracking.py` | Journey event tracking integration test'lar |

### Texnik Tafsilotlar

**Production Hardening Checklist**:
- [ ] Barcha unit test'lar pass (>90% coverage yangi kod uchun)
- [ ] Integration test'lar pass
- [ ] Redis connection failure graceful degradation
- [ ] PostgreSQL connection failure graceful degradation
- [ ] OpenAI API failure fallback (template messages)
- [ ] Bot restart — pending follow-up'lar davom etadi
- [ ] Concurrent scheduler instances — Redis lock bilan himoya
- [ ] Anti-spam limits ishlaydi (daily, hourly, cooldown)
- [ ] Business hours respect qilinadi
- [ ] Memory cleanup cron job sozlangan
- [ ] Monitoring: follow-up sent/cancelled/failed counts logged
- [ ] Sentry error tracking sozlangan

**Performance Benchmarks**:
- Event emit: <10ms (fire-and-forget)
- Memory read: <5ms (Redis hit), <50ms (DB fallback)
- Follow-up check cycle: <500ms (100 pending follow-up'lar uchun)
- Message compose: <3s (OpenAI), <1ms (template fallback)

### Test Qilish Usuli
```bash
# To'liq test suite
pytest tests/ -v --tb=short

# Coverage report
pytest tests/ --cov=core/services --cov-report=html

# Load test (agar kerak bo'lsa)
locust -f tests/load/test_followup_load.py
```

### Risk: LOW
- Faqat test'lar — production kodga ta'sir yo'q
- Coverage gap'larni aniqlash va to'ldirish

### Rollback Plan: N/A (test code)
### Dependencies: Barcha oldingi STEP'lar (A-I)
### Taxminiy Vaqt: 1.5 ish kuni

---

## Xulosa — Dependency Graph

```
STEP A (docs) ─────────────────────────────────────────────────────► Done
   │
   ▼
STEP B (events) ──────────────────────────────────────────────────►
   │                    │
   ▼                    ▼
STEP C (memory)    STEP H (admin notifications)
   │
   ▼
STEP D (scheduler) ────────────────────────────────────────────────►
   │         │         │
   ▼         ▼         ▼
STEP E     STEP F    STEP G        (parallel: catalog, price, abandoned)
   │         │         │
   └────┬────┘         │
        ▼              │
   STEP I (AI msg) ◄───┘
        │
        ▼
   STEP J (tests + hardening) ────────────────────────────────────► Done
```

### Parallel Execution Opportunities

| Parallel Group | STEP'lar | Shart |
|----------------|----------|-------|
| Group 1 | STEP E + F + G | STEP D tugagandan keyin |
| Group 2 | STEP H | STEP B tugagandan keyin (D ga bog'liq emas) |
| Group 3 | STEP I | STEP E/F/G dan kamida bittasi tugagandan keyin |

### Minimal Viable Agent (MVA) — 5 ish kuni

Agar tezroq natija kerak bo'lsa, quyidagi STEP'lar yetarli:
1. **STEP A** — Docs (0.5 kun)
2. **STEP B** — Events (2 kun)
3. **STEP D** — Scheduler (2 kun)
4. **STEP E** — Catalog follow-up (1 kun)

Bu 4 qadam bilan eng oddiy AI Agent ishlaydi: katalog ochgan mijozga 10 daqiqada follow-up yuboradi.

---

**Oldingi fayl**: [08_ADMIN_NOTIFICATIONS.md](./08_ADMIN_NOTIFICATIONS.md) | **Keyingi fayl**: [10_TEST_PLAN.md](./10_TEST_PLAN.md)
