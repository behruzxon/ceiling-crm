# AI Agent Arxitekturasi — To'liq Texnik Hujjat

## Umumiy Arxitektura Diagrammasi

```
                           TELEGRAM USER
                               |
                               v
                    +---------------------+
                    |   aiogram Handlers   |
                    |  (catalog, pricing,  |
                    |   order, ai_support, |
                    |   packages, operator)|
                    +----------+----------+
                               |
                    emit event  |
                               v
              +--------------------------------+
              |     A) EVENT COLLECTOR          |
              |   JourneyEventService           |
              |   (core/services/)              |
              +---------------+----------------+
                              |
                    event obj |
                              v
              +--------------------------------+
              |   B) JOURNEY STATE TRACKER      |
              |   JourneyStateService           |
              |   Redis (real-time) +           |
              |   PostgreSQL (persistence)      |
              +------+----------------+--------+
                     |                |
            state    |                | state change
            update   |                | event
                     v                v
              +-----------+    +------------------+
              | C) AGENT  |    | D) FOLLOW-UP     |
              |   MEMORY  |    |    SCHEDULER     |
              |           |    |  AgentFollowup   |
              | AgentMem  |    |  Scheduler       |
              | Service   |    | (APScheduler +   |
              |           |    |  Celery)         |
              +-----------+    +--------+---------+
                     |                  |
                     |         schedule |
                     |         delayed  |
                     |         task     |
                     v                  v
              +--------------------------------+
              |    E) MESSAGE COMPOSER          |
              |    MessageComposerService       |
              |    (context-aware, Uzbek)       |
              +---------------+----------------+
                              |
                    message + |  keyboard
                              v
              +--------------------------------+
              |         TELEGRAM USER          |
              |     (follow-up delivered)       |
              +--------------------------------+
                              |
                    no reply? | admin escalation?
                              v
              +--------------------------------+
              |    F) ADMIN ESCALATION          |
              |    (LeadNotificationService     |
              |     extended)                   |
              +--------------------------------+
                              |
              +--------------------------------+
              |    G) SAFETY GUARDRAILS         |
              |    Anti-spam, stop conditions,  |
              |    duplicate prevention         |
              +--------------------------------+
```

---

## A) Event Collector — Hodisa Yig'uvchi

### Vazifasi
Har bir muhim mijoz harakatini standart event formatiga o'girib, journey tracker va follow-up scheduler'ga yuboradi. Mavjud handler'larga yengil hook qo'shish orqali ishlaydi — handler logikasini o'zgartirmaydi.

### Mavjud Fayllar Bilan Bog'lanishi

| Handler fayl | Qaysi eventlar emit qilinadi |
|-------------|-------------------------------|
| `apps/bot/handlers/private/catalog.py` | `OPENED_CATALOG`, `VIEWED_CATALOG_ITEM` |
| `apps/bot/handlers/private/pricing.py` | `USED_PRICE_CALCULATOR`, `PRICE_CALCULATED` |
| `apps/bot/handlers/private/order.py` | `CLICKED_ORDER`, `ORDER_FORM_STARTED`, `ORDER_FORM_ABANDONED` |
| `apps/bot/handlers/private/ai_support.py` | `PHONE_SHARED`, `IMAGE_SENT`, `AI_QUESTION_ASKED` |
| `apps/bot/handlers/private/packages.py` | `VIEWED_PACKAGES`, `PACKAGE_SELECTED` |
| `apps/bot/handlers/private/operator.py` | `OPERATOR_REQUESTED` |
| `apps/bot/handlers/private/support.py` | `STARTED_BOT` (/start command) |
| `apps/bot/handlers/private/lead_capture.py` | `LOCATION_SHARED`, `LEAD_CAPTURED` |
| `apps/bot/handlers/private/measurement_lead.py` | `MEASUREMENT_REQUESTED` |
| `apps/bot/handlers/callbacks/pipeline_callbacks.py` | `DEAL_CLOSED`, `LOST_LEAD` |
| `apps/bot/handlers/callbacks/kanban_callbacks.py` | `STAGE_CHANGED` |

### Yangi Fayl Taklifi

**`core/services/journey_event_service.py`**

```python
@dataclass(frozen=True, slots=True)
class JourneyEvent:
    event_type: str          # "OPENED_CATALOG", "PRICE_CALCULATED", etc.
    user_id: int             # Telegram user ID
    timestamp: datetime      # UTC
    data: dict[str, Any]     # event-specific payload
    source_handler: str      # "catalog.py", "pricing.py", etc.

class JourneyEventService:
    async def emit(self, event: JourneyEvent) -> None:
        """
        1. Persist event to journey_events table
        2. Update journey state via JourneyStateService
        3. Update agent memory via AgentMemoryService
        4. Schedule follow-ups via AgentFollowupScheduler
        5. Notify admin if escalation needed
        """
```

### Data Flow
```
Handler (catalog.py) -> JourneyEvent(OPENED_CATALOG, user_id, {design_name: "Hi Tech"})
  -> JourneyEventService.emit()
    -> PostgreSQL: journey_events INSERT
    -> JourneyStateService: IDLE -> BROWSING
    -> AgentMemoryService: interested_design = "Hi Tech"
    -> AgentFollowupScheduler: schedule catalog_followup in 10 min
```

### Mavjud Integratsiya Nuqtalari

Mavjud `core/events/bus.py` event bus ishlatiladi. Hozirda bus quyidagi eventlarni qo'llab-quvvatlaydi:
- `LeadCreated`
- `StageChanged`
- `AppointmentBooked`
- `BroadcastCompleted`

Yangi eventlar qo'shiladi:
- `JourneyEventEmitted` — yangi journey event chiqdi
- `FollowupScheduled` — follow-up rejalashtirildi
- `FollowupSent` — follow-up yuborildi

---

## B) Journey State Tracker — Sayohat Holat Kuzatuvchisi

### Vazifasi
Har bir foydalanuvchi uchun journey state machine boshqaradi. Mijoz hozir qaysi bosqichdda ekanini aniqlaydi va state o'zgarishini trigger qiladi.

### State Machine

```
                 +--------+
                 |  IDLE  |
                 +---+----+
                     |
          /start     | STARTED_BOT
                     v
              +----------+
              | BROWSING  |<──────────────────┐
              +-----+----+                    |
                    |                         |
       OPENED_CATALOG, VIEWED_CATALOG_ITEM    |
                    |                         |
                    v                         |
            +-------------+                   |
            | CALCULATING |                   |
            +------+------+                   |
                   |                          |
      PRICE_CALCULATED                        |
                   |                          |
                   v                          |
            +-----------+                     |
            | ORDERING  |─────────────────────┘
            +-----+-----+    (abandoned -> back to BROWSING)
                  |
       ORDER_COMPLETED / PHONE_SHARED
                  |
                  v
           +------------+
           | CONTACTED  |
           +------+-----+
                  |
         DEAL_CLOSED  |  LOST_LEAD
              |              |
              v              v
        +-----------+  +--------+
        | CONVERTED |  |  LOST  |
        +-----------+  +--------+
```

### Transition Qoidalari

| Hozirgi State | Event | Yangi State | Shart |
|---------------|-------|-------------|-------|
| IDLE | STARTED_BOT | IDLE | Har doim |
| IDLE | OPENED_CATALOG | BROWSING | — |
| IDLE | USED_PRICE_CALCULATOR | CALCULATING | — |
| IDLE | CLICKED_ORDER | ORDERING | — |
| BROWSING | USED_PRICE_CALCULATOR | CALCULATING | — |
| BROWSING | CLICKED_ORDER | ORDERING | — |
| BROWSING | OPENED_CATALOG | BROWSING | State o'zgarmaydi, timer reset |
| CALCULATING | PRICE_CALCULATED | CALCULATING | Timer reset |
| CALCULATING | CLICKED_ORDER | ORDERING | — |
| CALCULATING | OPENED_CATALOG | BROWSING | Qayta katalogga ketdi |
| ORDERING | ORDER_FORM_ABANDONED (10 min) | BROWSING | Timeout |
| ORDERING | PHONE_SHARED | CONTACTED | — |
| ANY | OPERATOR_REQUESTED | CONTACTED | Admin olib boradi |
| ANY | DEAL_CLOSED | CONVERTED | Terminal state |
| ANY | LOST_LEAD | LOST | Terminal state |

### Mavjud Fayllar Bilan Bog'lanishi

- **Redis**: hozirgi state real vaqtda `CacheKeys` orqali saqlanadi
- **PostgreSQL**: `customer_journey_states` jadvalida persistensiya
- **Mavjud ai_followup_state**: `CacheKeys.ai_followup_state(user_id)` — bu hozirgi follow-up state'ni saqlaydi (`{first_sent, second_sent, lead_created}`). Yangi journey state bu bilan birga ishlaydi, o'rnini oladi emas

### Yangi Fayl Taklifi

**`core/services/journey_state_service.py`**

```python
class JourneyState(str, Enum):
    IDLE = "idle"
    BROWSING = "browsing"
    CALCULATING = "calculating"
    ORDERING = "ordering"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    LOST = "lost"

class JourneyStateService:
    async def get_state(self, user_id: int) -> JourneyState:
        """Redis'dan hozirgi state'ni olish."""

    async def transition(self, user_id: int, event: JourneyEvent) -> JourneyState | None:
        """Event asosida state o'tkazish. None qaytarsa — o'tish yo'q."""

    async def persist(self, user_id: int, state: JourneyState) -> None:
        """PostgreSQL'ga state yozish (Redis crash himoyasi)."""
```

**Yangi Redis key**:
```python
# infrastructure/cache/keys.py ga qo'shiladi
CacheKeys.journey_state(user_id) -> f"journey:state:{user_id}"
CacheTTL.JOURNEY_STATE = 2_592_000  # 30 kun
```

**Yangi PostgreSQL table**:
```sql
-- Alembic migration
CREATE TABLE customer_journey_states (
    user_id BIGINT PRIMARY KEY,
    current_state VARCHAR(20) NOT NULL DEFAULT 'idle',
    previous_state VARCHAR(20),
    last_event_type VARCHAR(50),
    last_event_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_cjs_state ON customer_journey_states(current_state);
CREATE INDEX ix_cjs_updated ON customer_journey_states(updated_at);
```

---

## C) Agent Memory — Agent Xotirasi

### Vazifasi
Har bir foydalanuvchi uchun tuzilgan (structured) xotira saqlaydi. Mavjud `CacheKeys.ai_memory` ni kengaytiradi — hozirgi memory tuzilmasi saqlanib qoladi, yangi maydonlar qo'shiladi.

### Mavjud Memory Tuzilmasi (ai_memory.py)

Hozirda `CacheKeys.ai_memory(user_id)` quyidagi JSON saqlaydi:
```json
{
    "name": "Bekzod",
    "district": "Qarshi",
    "area_m2": 25.0,
    "design_type": "Hi Tech",
    "lead_score": 65,
    "last_user_message": "narx qancha",
    "phone_captured": true,
    "updated_at": 1716600000,
    "created_at": 1716500000,
    "buyer_type": "quality_buyer",
    "last_objection": "expensive",
    "last_objection_severity": "moderate",
    "last_intent": "price",
    "last_closing_attempt": "book_measurement",
    "last_closing_at": 1716590000,
    "last_negotiation_tactic": "value_reframe",
    "negotiation_escalated": false,
    "lead_temperature": "warm",
    "closing_confidence": 0.65
}
```

### Kengaytirilgan Memory (Yangi Maydonlar)

```json
{
    // ... mavjud maydonlar saqlanadi ...

    "journey_state": "calculating",
    "last_event": "PRICE_CALCULATED",
    "last_event_at": 1716600000,

    "interested_designs": ["Hi Tech", "Mramor"],
    "viewed_catalog_items": 3,
    "price_quotes_received": 1,
    "last_price_quote": {
        "design": "Hi Tech",
        "area_m2": 25.0,
        "total_price": 2500000,
        "timestamp": 1716600000
    },

    "order_form_progress": {
        "started_at": 1716600000,
        "last_step": "waiting_for_district",
        "completed_steps": ["name", "phone"],
        "remaining_steps": ["district", "category", "area"]
    },

    "follow_up_history": [
        {"type": "catalog_followup", "sent_at": 1716590000, "replied": false},
        {"type": "price_followup", "sent_at": 1716595000, "replied": true}
    ],

    "intent_history": ["catalog", "price", "price", "order"],

    "stop_follow_ups": false,
    "stop_reason": null
}
```

### Mavjud Fayllar Bilan Bog'lanishi

- **`apps/bot/handlers/private/ai_memory.py`** — hozirgi `_load_ai_memory()` va `_save_ai_memory()` funksiyalari. Yangi AgentMemoryService bu funksiyalarni ishlatadi, o'rnini oladi emas
- **`infrastructure/cache/keys.py`** — `CacheKeys.ai_memory(user_id)`, TTL 30 kun. Shu key ishlatiladi, yangi key yaratilmaydi
- **`infrastructure/database/models/ai_memory.py`** — `AiMemoryModel` (PostgreSQL backup). Profile JSON kolonnasi kengaytiriladi

### Yangi Fayl Taklifi

**`core/services/agent_memory_service.py`**

```python
class AgentMemoryService:
    async def load(self, user_id: int) -> dict[str, Any]:
        """Redis'dan memory yuklash, yo'q bo'lsa PostgreSQL'dan."""

    async def save(self, user_id: int, memory: dict[str, Any]) -> None:
        """Redis + PostgreSQL'ga yozish."""

    async def update_from_event(self, user_id: int, event: JourneyEvent) -> None:
        """Event asosida memory yangilash."""

    async def record_follow_up(self, user_id: int, fu_type: str, sent_at: int) -> None:
        """Follow-up yuborilgani haqida yozish."""

    async def should_stop_follow_ups(self, user_id: int) -> tuple[bool, str | None]:
        """Follow-up to'xtatish kerakmi tekshirish. (bool, reason)"""
```

### Data Flow
```
Event(PRICE_CALCULATED) -> AgentMemoryService.update_from_event()
  -> Load existing memory from Redis
  -> Merge: journey_state = "calculating"
  -> Merge: last_event = "PRICE_CALCULATED"
  -> Merge: last_price_quote = {design, area, price, ts}
  -> Merge: intent_history.append("price")
  -> Save to Redis + PostgreSQL
```

---

## D) Follow-up Scheduler — Kechiktirilgan Harakatlar Rejalashtiruvchisi

### Vazifasi
Event-driven delayed actions boshqaradi. Har bir event uchun mos follow-up ni to'g'ri vaqtda rejalashtiradi, mavjud APScheduler + Celery infratuzilmasi bilan integratsiya qiladi.

### Mavjud Follow-up Mexanizmlari

Hozirda 3 ta alohida follow-up mexanizm bor:

1. **`ai_followups.py` — asyncio.sleep based**
   - `_catalog_followup_task`: 5-10 min delay (random), Redis NX dedup
   - `_ai_followup_task`: 10 min (1st) + 60 min (2nd), nonce-based cancel
   - Muammo: `asyncio.sleep` bot restart'da yo'qoladi

2. **`followup_service.py` — APScheduler based (60s interval)**
   - `process_due_followups()`: `next_follow_up_at` column asosida
   - Brain-driven: `FollowupBrainService` qaysi turdagi follow-up yuborish kerakligini aniqlaydi
   - Max 5 follow-up per lead (hard cap)

3. **`followup_jobs.py` — APScheduler interval jobs**
   - `check_inactive_leads`: 15 daqiqada — 24h/72h/7d tiered reminders
   - `check_hot_lead_inactivity`: 10 daqiqada — HOT leadlar 2h+ inactive alert

### Yangi: Unified Follow-up Scheduler

Barcha follow-up mexanizmlarni bitta tizimga birlashtirish. Mavjud mexanizmlar ishlashda davom etadi — yangi tizim ular ustida qo'shimcha qatlam sifatida ishlaydi.

### Mavjud Fayllar Bilan Bog'lanishi

- **`apps/scheduler/main.py`** — APScheduler entry point. Yangi job qo'shiladi
- **`apps/scheduler/jobs/followup_jobs.py`** — mavjud 3 ta job. Yangi job qo'shiladi
- **`infrastructure/queue/tasks/`** — Celery tasks. Yangi delayed task qo'shiladi
- **`infrastructure/cache/keys.py`** — Redis dedup keys. Yangi key'lar qo'shiladi

### Yangi Fayl Taklifi

**`core/services/agent_followup_scheduler.py`**

```python
@dataclass(frozen=True, slots=True)
class ScheduledFollowup:
    user_id: int
    follow_up_type: str     # "catalog", "price", "abandoned_order", etc.
    fire_at: datetime       # UTC
    event_type: str         # trigger event
    message_template: str   # message key
    metadata: dict          # event-specific data for personalization

class AgentFollowupScheduler:
    async def schedule(self, followup: ScheduledFollowup) -> bool:
        """
        1. Check cooldown (Redis NX)
        2. Check max count per type per day
        3. Check stop conditions
        4. Defer to business hours if needed
        5. Write to scheduled_followups table
        6. Create Celery delayed task OR APScheduler one-shot job
        """

    async def cancel_user_followups(self, user_id: int, reason: str) -> int:
        """Cancel all pending follow-ups for a user. Returns count cancelled."""

    async def cancel_by_type(self, user_id: int, follow_up_type: str) -> bool:
        """Cancel specific follow-up type."""
```

**`apps/scheduler/jobs/agent_followup_jobs.py`**

```python
def register_agent_followup_jobs(scheduler: AsyncIOScheduler) -> None:
    # Process scheduled follow-ups every 30 seconds
    scheduler.add_job(
        process_agent_followups,
        trigger="interval",
        seconds=30,
        id="process_agent_followups",
        replace_existing=True,
    )

async def process_agent_followups() -> None:
    """
    1. Query scheduled_followups WHERE fire_at <= now AND status = 'pending'
    2. For each: compose message, send, update status
    3. Check for admin escalation triggers
    """
```

### Data Flow
```
Event(PRICE_CALCULATED) -> AgentFollowupScheduler.schedule()
  -> Check: cooldown key "agent:fu:price:{user_id}" exists? (Redis NX)
  -> Check: today's count < 3? (Redis INCR with 24h TTL)
  -> Check: user didn't say "kerak emas"? (AgentMemoryService)
  -> Check: business hours? (shared/utils/business_hours.py)
  -> INSERT INTO scheduled_followups (user_id, type, fire_at, status='pending')
  -> Celery: send_agent_followup.apply_async(eta=fire_at)
     OR
  -> APScheduler: add_job(send_followup, run_date=fire_at, id=unique_key)
```

**Yangi Redis keys**:
```python
# infrastructure/cache/keys.py ga qo'shiladi
CacheKeys.agent_followup_cooldown(user_id, fu_type) -> f"agent:fu:{fu_type}:{user_id}"
CacheKeys.agent_followup_daily_count(user_id) -> f"agent:fu:daily:{user_id}"
CacheTTL.AGENT_FOLLOWUP_COOLDOWN_CATALOG = 86_400   # 24h
CacheTTL.AGENT_FOLLOWUP_COOLDOWN_PRICE = 7_200      # 2h
CacheTTL.AGENT_FOLLOWUP_COOLDOWN_ORDER = 21_600     # 6h
CacheTTL.AGENT_FOLLOWUP_DAILY_COUNT = 90_000        # 25h
```

**Yangi PostgreSQL table**:
```sql
CREATE TABLE scheduled_followups (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    follow_up_type VARCHAR(30) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    fire_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(15) NOT NULL DEFAULT 'pending',  -- pending, sent, cancelled, expired
    message_key VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    cancel_reason VARCHAR(100)
);
CREATE INDEX ix_sf_fire ON scheduled_followups(fire_at) WHERE status = 'pending';
CREATE INDEX ix_sf_user ON scheduled_followups(user_id, status);
```

---

## E) Message Composer — Xabar Tuzuvchi

### Vazifasi
Follow-up uchun kontekst-aware, tabiiy Uzbek tilida xabarlar tuzadi. Mavjud system prompt + yangi follow-up specific promptlar ishlatadi. Agent memory'dan shaxsiylashtirilgan xabarlar yaratadi.

### Mavjud Fayllar Bilan Bog'lanishi

- **`apps/bot/ai/system_prompt.py`** — Madina system prompt. Follow-up xabarlari shu persona'da yoziladi
- **`apps/bot/handlers/private/ai_states.py`** — `_AI_FOLLOWUP_MSG_1`, `_AI_FOLLOWUP_MSG_2` — hozirgi follow-up shablonlari
- **`core/services/followup_brain_service.py`** — `_FU_MESSAGES` dict — 6 ta follow-up turi uchun xabarlar
- **`shared/knowledge/uz.md`** — mahsulot bilimi. Xabarlarda ishlatiladi

### Yangi Fayl Taklifi

**`core/services/message_composer_service.py`**

```python
class MessageComposerService:
    def compose_follow_up(
        self,
        follow_up_type: str,
        memory: dict[str, Any],
        event_data: dict[str, Any],
    ) -> ComposedMessage:
        """
        Memory'dan shaxsiylashtirilgan follow-up xabari tuzish.

        Returns:
            ComposedMessage(text, keyboard, parse_mode)
        """

    def _personalize(self, template: str, memory: dict) -> str:
        """Template'ga memory ma'lumotlarini kiritish."""
        # {name} -> Bekzod
        # {design_name} -> Hi Tech
        # {area} -> 25
        # {price} -> 2,500,000
        # {remaining_steps} -> 3

@dataclass(frozen=True, slots=True)
class ComposedMessage:
    text: str
    keyboard: InlineKeyboardMarkup | None
    parse_mode: str = "HTML"
```

### Message Shablonlari (Uzbek, Tabiiy Ton)

```python
FOLLOW_UP_TEMPLATES = {
    "catalog_followup": (
        "Salom {name} 😊 Katalogdagi qaysi model sizga yoqdi? "
        "Xonangiz kvadratini yozsangiz, taxminiy narxni "
        "1 daqiqada hisoblab beraman."
    ),
    "price_followup": (
        "💰 {design_name} uchun {area}m² narxi — {price} so'm. "
        "Hozir buyurtma bersangiz bepul o'lchov + 15 yil kafolat! "
        "Buyurtma berasizmi? 👇"
    ),
    "abandoned_order_followup": (
        "📝 Buyurtmangiz yarim qoldi! Davom etasizmi? "
        "Qolgan {remaining_steps} qadam qoldi. "
        "Tayyor paketlarimizni ko'rishni xohlaysizmi?"
    ),
    "phone_reminder": (
        "Salom {name}! Narx hisoblagansiz — aniqroq ma'lumot "
        "uchun telefon raqamingizni yuboring 📱\n"
        "Ustamiz bepul o'lchov qilib beradi!"
    ),
    "soft_24h_reminder": (
        "Salom {name}! 🙂 Natijnoy potolok bo'yicha "
        "savollaringiz qoldimi? Men yordam berishga tayyorman."
    ),
    "final_72h_offer": (
        "Salom {name}! Sizga maxsus taklif: "
        "bugun buyurtma bersangiz 5% chegirma! 🎁\n"
        "Qiziqsangiz yozing."
    ),
    "image_admin_alert": (
        "📸 Mijoz xona rasmini yubordi — tezda ko'ring!"
    ),
}
```

### Data Flow
```
AgentFollowupScheduler -> process_agent_followups()
  -> Load memory from AgentMemoryService
  -> MessageComposerService.compose_follow_up(type, memory, event_data)
  -> Personalize template: {name} = "Bekzod", {price} = "2,500,000"
  -> Add inline keyboard: [Buyurtma] [Operator] [Kerak emas]
  -> Bot.send_message(chat_id, composed.text, reply_markup=composed.keyboard)
```

---

## F) Admin Escalation — Admin Eskalatsiyasi

### Vazifasi
Enriched lead card'larni admin guruhga yuboradi. Mavjud `LeadNotificationService` kengaytiradi — journey summary, suggested action va clickable phone qo'shiladi.

### Mavjud Fayllar Bilan Bog'lanishi

- **`core/services/lead_notification_service.py`** — `notify_new_lead()`, `notify_hot_lead()`. Mavjud keyboard: Kanban, Bog'landim, O'lchov, Narx, Zakaz tugmalari
- **`apps/bot/handlers/private/ai_notifications.py`** — `_notify_ai_lead_collected()` — 5 layer notification: scoring + probability + buyer + revenue + negotiation
- **`infrastructure/di.py`** — `get_lead_notification_service()` factory

### Yangi Qo'shimchalar (Mavjud Servisga)

```python
# LeadNotificationService ga yangi method qo'shiladi:

async def notify_journey_escalation(
    self,
    user_id: int,
    escalation_type: str,  # "abandoned_order", "hot_no_response", "repeated_objection"
    journey_summary: dict,
    suggested_action: str,
) -> None:
    """
    Journey-based admin escalation.

    Card format:
    ━━━━━━━━━━━━━━━━━━━━━━
    🚨 ESKALATSIYA: Buyurtma tashlab ketdi

    👤 Bekzod | +998901234567
    📍 Qarshi tumani
    📊 Score: 72 | 🔥 HOT

    📋 Journey:
    ├ Katalog ko'rdi (14:30)
    ├ Narx hisoblatdi: Hi Tech 25m² = 2.5M (14:35)
    ├ Buyurtma boshladi (14:40)
    └ ❌ Yarim qoldirdi: district bosqichida (14:50)

    💡 Tavsiya: Telefon qilish — narx tasdiqlanagan,
       faqat tuman va vaqtni kelishish kerak

    [📌 Kanbanda ochish] [📞 Qo'ng'iroq]
    ━━━━━━━━━━━━━━━━━━━━━━
    """
```

### Data Flow
```
AgentFollowupScheduler -> 2nd price followup no response?
  -> Admin escalation triggered
  -> Load memory + journey events
  -> Build journey summary (timeline format)
  -> Build suggested action (from lead signals)
  -> LeadNotificationService.notify_journey_escalation()
  -> Bot.send_message(admin_group_id, enriched_card)
```

---

## G) Safety Guardrails — Xavfsizlik Himoyalari

### Vazifasi
Spam oldini olish, to'xtatish shartlarini tekshirish va dublikat follow-up'larni bloklash.

### Mavjud Himoyalar

| Himoya | Fayl | Mexanizm |
|--------|------|----------|
| Max 5 follow-up per lead | `followup_service.py` | `_MAX_FOLLOWUP_COUNT = 5` |
| Follow-up brain skip | `followup_brain_service.py` | `_check_skip()` — cold + cooling + low score |
| Catalog dedup | `ai_followups.py` | Redis NX `madina:catalog_followup:{user_id}` 24h |
| AI followup nonce | `ai_followups.py` | Nonce mismatch = cancel |
| Sales closer cooldown | `keys.py` | `closer:last:{user_id}` 10min NX |
| Rate limit | `ai_support.py` | `_AI_DAILY_LIMIT = 100` per user |
| Business hours | `followup_brain_service.py` | `defer_to_business_hours()` |
| Auto-reply consecutive cap | `ai_support.py` | Redis counter per user |

### Yangi Himoyalar

```python
# Anti-spam qoidalar
AGENT_SAFETY_RULES = {
    # Max follow-ups per user per day (all types combined)
    "max_followups_per_day": 3,

    # Max follow-ups per event type per user
    "max_per_event_type": {
        "catalog_followup": 1,      # 1 per 24h
        "price_followup": 2,        # 2 per 24h
        "abandoned_order": 1,       # 1 per abandoned form
        "phone_reminder": 1,        # 1 per price calc session
        "soft_24h_reminder": 1,     # 1 per 24h period
        "final_72h_offer": 1,       # 1 per 72h period
    },

    # Minimum cooldown between any follow-up (seconds)
    "min_cooldown_seconds": 3600,   # 1 hour

    # Stop conditions — follow-up immediately cancelled
    "stop_conditions": [
        "user_replied",             # mijoz javob berdi
        "user_ordered",             # buyurtma berdi
        "user_said_no",             # "kerak emas", "yo'q", "boshlama"
        "operator_requested",       # operator so'radi
        "deal_closed",              # pipeline -> DEAL
        "lead_lost",                # pipeline -> LOST
        "user_blocked_bot",         # TelegramForbiddenError
    ],

    # Max follow-up chain length per user
    "max_chain_length": 5,

    # Quiet hours (in addition to business hours)
    "quiet_start_hour": 21,         # 21:00 Toshkent
    "quiet_end_hour": 9,            # 09:00 Toshkent
}
```

### Stop Condition Detection

```python
# Har bir follow-up yuborishdan oldin tekshiriladi:

async def check_stop_conditions(user_id: int) -> tuple[bool, str | None]:
    """Return (should_stop, reason)."""

    # 1. User blocked bot?
    #    -> TelegramForbiddenError catch qilinadi

    # 2. User replied since last follow-up?
    #    -> ai_last_interaction timestamp vs last follow-up timestamp

    # 3. User ordered?
    #    -> lead.lead_status in ("deal", "contacted") OR pipeline DEAL/INSTALLATION/COMPLETED

    # 4. User said "kerak emas"?
    #    -> memory.stop_follow_ups == True

    # 5. Operator requested?
    #    -> memory.last_event == "OPERATOR_REQUESTED"

    # 6. Pipeline terminal?
    #    -> lead in DEAL/COMPLETED/LOST stage
```

### Redis Key Pattern for Dedup

```python
# Barcha agent follow-up dedup key'lari:

# Per-type cooldown (prevents same type twice within cooldown)
f"agent:fu:{fu_type}:{user_id}"  # TTL: type-specific (1h - 24h)

# Daily counter (prevents more than 3 per day)
f"agent:fu:daily:{user_id}"      # TTL: 25h (auto-expire past midnight)

# Per-event dedup (prevents duplicate for same trigger event)
f"agent:fu:event:{event_id}"     # TTL: 24h

# Global last follow-up timestamp
f"agent:fu:last:{user_id}"       # TTL: 1h (minimum gap between any follow-up)
```

### Mavjud Fayllar Bilan Bog'lanishi

- **`infrastructure/cache/keys.py`** — yangi dedup key'lar qo'shiladi
- **`shared/utils/business_hours.py`** — `is_off_hours()`, `defer_to_business_hours()` funksiyalari ishlatiladi
- **`core/services/followup_brain_service.py`** — `_check_skip()` logikasi reference sifatida ishlatiladi

### Yangi Fayl Taklifi

**`core/services/agent_safety_service.py`**

```python
class AgentSafetyService:
    async def can_send_followup(
        self,
        user_id: int,
        follow_up_type: str,
        memory: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """
        Barcha xavfsizlik tekshiruvlarini o'tkazish.
        Returns: (can_send, rejection_reason)

        Tekshiruv tartibi:
        1. Stop conditions (terminal — hech qachon yuborma)
        2. Business hours (deferrable — keyinga surish mumkin)
        3. Daily limit (terminal — bugunlik yetarli)
        4. Per-type cooldown (terminal — hali erta)
        5. Min cooldown between any follow-up (terminal)
        """

    async def record_sent(self, user_id: int, follow_up_type: str) -> None:
        """Follow-up yuborilgani qayd qilish (dedup key'lar set qilish)."""

    async def mark_stop(self, user_id: int, reason: str) -> None:
        """Barcha follow-up'larni to'xtatish (user said no, ordered, etc.)."""
```

---

## DI Integratsiya

Yangi servislar `infrastructure/di.py` ga qo'shiladi:

```python
# infrastructure/di.py ga yangi factory'lar:

def get_journey_event_service(session: AsyncSession) -> JourneyEventService:
    return JourneyEventService(session)

def get_journey_state_service() -> JourneyStateService:
    return JourneyStateService()

def get_agent_memory_service() -> AgentMemoryService:
    return AgentMemoryService()

def get_agent_followup_scheduler(session: AsyncSession) -> AgentFollowupScheduler:
    return AgentFollowupScheduler(session)

def get_message_composer_service() -> MessageComposerService:
    return MessageComposerService()

def get_agent_safety_service() -> AgentSafetyService:
    return AgentSafetyService()
```

---

## Fayl Xaritasi (File Map)

```
core/services/
    journey_event_service.py        # A) Event Collector
    journey_state_service.py        # B) Journey State Tracker
    agent_memory_service.py         # C) Agent Memory
    agent_followup_scheduler.py     # D) Follow-up Scheduler
    message_composer_service.py     # E) Message Composer
    agent_safety_service.py         # G) Safety Guardrails

apps/scheduler/jobs/
    agent_followup_jobs.py          # D) Scheduler job registration

infrastructure/cache/keys.py       # Yangi CacheKeys + CacheTTL (kengaytirish)
infrastructure/di.py               # Yangi factory funksiyalar (kengaytirish)

# Alembic migration (yangi jadvallar):
#   customer_journey_states
#   journey_events
#   scheduled_followups
```

---

**Keyingi fayl**: [02_CUSTOMER_JOURNEY_TRACKING.md](./02_CUSTOMER_JOURNEY_TRACKING.md) — batafsil event tracking
