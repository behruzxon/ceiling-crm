# Customer Journey Tracking — Batafsil Event Kuzatuv

## 1. Journey Events Jadvali

Har bir event quyidagi tuzilmada saqlanadi:

```python
@dataclass(frozen=True, slots=True)
class JourneyEvent:
    event_type: str          # unikal event identifikatori
    user_id: int             # Telegram user ID
    timestamp: datetime      # UTC
    data: dict[str, Any]     # event-specific payload
    source_handler: str      # qaysi handler/fayl trigger qildi
    dedup_key: str | None    # Redis NX dedup kaliti (dublikat oldini olish)
```

---

## 2. Batafsil Event Ro'yxati

### 2.1. STARTED_BOT

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `STARTED_BOT` |
| **Qachon trigger bo'ladi** | `/start` command — `apps/bot/handlers/private/support.py` `cmd_start()` handler. Deep link payload borligini `message.text` dan parse qiladi |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `source` ("deep_link" yoki "organic"), `deep_link_payload` (agar bor bo'lsa: "zakaz", "price", "katalog", "paketlar", "ai", etc.) |
| **Keyingi agent action** | Journey state = IDLE ga set qilish. Agent memory init qilish (agar yangi user). Agar deep link = "price" bo'lsa — CALCULATING ga o'tish. Agar "katalog" — BROWSING ga o'tish |
| **Redis key** | `journey:state:{user_id}` — state IDLE ga set qilinadi. Dedup kerak emas (/start qayta-qayta bosilishi mumkin) |

**Handler fayl**: `apps/bot/handlers/private/support.py`
```python
# Mavjud cmd_start() da qo'shiladi:
async def cmd_start(message: Message, state: FSMContext, **data):
    # ... mavjud kod ...
    # YANGI: journey event emit
    await journey_event_service.emit(JourneyEvent(
        event_type="STARTED_BOT",
        user_id=message.from_user.id,
        timestamp=datetime.now(timezone.utc),
        data={"source": "deep_link" if payload else "organic", "payload": payload},
        source_handler="support.py",
    ))
```

---

### 2.2. OPENED_CATALOG

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `OPENED_CATALOG` |
| **Qachon trigger bo'ladi** | `BTN_CATALOG` tugma bosildi yoki `/catalog` command — `apps/bot/handlers/private/catalog.py` `cmd_catalog()` handler. Shuningdek `ai_support.py` `_is_catalog_request()` orqali AI chatda katalog so'ralganda |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `entry_point` ("button" / "command" / "ai_chat") |
| **Keyingi agent action** | Journey state = BROWSING ga set. 10 daqiqalik follow-up taymer boshlash. Agar 10 daqiqa ichida keyingi harakat bo'lmasa — catalog_followup trigger bo'ladi |
| **Redis key** | `agent:fu:catalog:{user_id}` — 24h TTL, NX flag. Agar allaqachon set bo'lsa — follow-up rejalashtirilmaydi (kuniga 1 marta) |

**Handler fayl**: `apps/bot/handlers/private/catalog.py`
```python
# Mavjud cmd_catalog() da qo'shiladi:
@router.message(F.chat.type.in_(_CHAT_TYPES), F.text == BTN_CATALOG)
@router.message(F.chat.type.in_(_CHAT_TYPES), Command("catalog"))
async def cmd_catalog(message: Message, state: FSMContext, **data):
    await state.set_state(CatalogStates.waiting_for_design)
    await message.answer("📂 <b>Katalog</b>\n\nDizaynni tanlang:", reply_markup=catalog_design_keyboard())
    # YANGI: journey event
    if message.from_user:
        asyncio.create_task(journey_event_service.emit(JourneyEvent(
            event_type="OPENED_CATALOG",
            user_id=message.from_user.id,
            timestamp=datetime.now(timezone.utc),
            data={"entry_point": "button"},
            source_handler="catalog.py",
        )))
```

Shuningdek `ai_support.py` da `_is_catalog_request()` ichida:
```python
# ai_support.py handle_ai_question() va handle_ai_message() da
if _is_catalog_request(text):
    # ... mavjud kod ...
    # YANGI: journey event
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="OPENED_CATALOG",
        user_id=user_id,
        data={"entry_point": "ai_chat"},
        source_handler="ai_support.py",
    )))
```

---

### 2.3. VIEWED_CATALOG_ITEM

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `VIEWED_CATALOG_ITEM` |
| **Qachon trigger bo'ladi** | Katalog design tugmasi bosilganda — `apps/bot/handlers/private/catalog.py` da design tanlash handler. `CatalogStates.waiting_for_design` da user design title'ni yozadi |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `design_name` (masalan: "Hi Tech", "Mramor"), `catalog_section` |
| **Keyingi agent action** | Agent memory'da `interested_designs` ro'yxatiga qo'shish. `viewed_catalog_items` counter increment. 10 daqiqalik follow-up taymer reset (qayta boshlanadi) |
| **Redis key** | Alohida dedup kerak emas — `OPENED_CATALOG` ning 24h dedup key'i catalog follow-up uchun yetarli |

**Handler fayl**: `apps/bot/handlers/private/catalog.py`
```python
# Design tanlash handler da qo'shiladi (CatalogStates.waiting_for_design state):
async def handle_design_selection(message: Message, state: FSMContext, **data):
    design_title = message.text
    section = _CATALOG_BY_TITLE.get(design_title)
    if section:
        # ... mavjud kod (rasm + caption yuborish) ...
        # YANGI: journey event
        asyncio.create_task(journey_event_service.emit(JourneyEvent(
            event_type="VIEWED_CATALOG_ITEM",
            user_id=message.from_user.id,
            data={"design_name": design_title, "catalog_section": section.key},
            source_handler="catalog.py",
        )))
```

---

### 2.4. USED_PRICE_CALCULATOR

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `USED_PRICE_CALCULATOR` |
| **Qachon trigger bo'ladi** | `BTN_PRICE` tugma yoki `/price` command — `apps/bot/handlers/private/pricing.py` `start_pricing_flow()`. Shuningdek `ai_support.py` da `_is_price_query()` orqali AI chatda narx so'ralganda |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `entry_point` ("button" / "command" / "ai_chat" / "callback") |
| **Keyingi agent action** | Journey state = CALCULATING ga set. 10 daqiqalik taymer boshlash (lekin hali narx chiqmagan — PRICE_CALCULATED ni kutish) |
| **Redis key** | `journey:state:{user_id}` — state CALCULATING ga yangilanadi |

**Handler fayl**: `apps/bot/handlers/private/pricing.py`
```python
# start_pricing_flow() da:
async def start_pricing_flow(message: Message, state: FSMContext):
    await state.set_state(PricingStates.waiting_for_length)
    # ... mavjud kod ...
    # YANGI: journey event
    if message.from_user:
        asyncio.create_task(journey_event_service.emit(JourneyEvent(
            event_type="USED_PRICE_CALCULATOR",
            user_id=message.from_user.id,
            data={"entry_point": "button"},
            source_handler="pricing.py",
        )))
```

---

### 2.5. PRICE_CALCULATED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `PRICE_CALCULATED` |
| **Qachon trigger bo'ladi** | Narx hisoblanib ko'rsatilgandan keyin — `apps/bot/handlers/private/pricing.py` da design tanlangandan keyin narx chiqarilganda. Shuningdek `ai_support.py` `_show_price_upsell()` (`ai_pricing_helpers.py`) orqali AI chatda narx hisoblaganda |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `area_m2`, `design_name`, `total_price` (UZS), `discount_percent`, `has_promo` |
| **Keyingi agent action** | Agent memory update: `last_price_quote = {design, area, price, ts}`. 10 daqiqalik price follow-up taymer boshlash. Agar 10 daqiqa ichida buyurtma boshlamasa — price_followup yuboriladi |
| **Redis key** | `agent:fu:price:{user_id}` — 2h TTL, NX. Har 2 soatda max 1 price follow-up |

**Handler fayl**: `apps/bot/handlers/private/pricing.py` (design callback handler)
```python
# Design callback da narx hisoblangandan keyin:
async def cb_design_chosen(callback: CallbackQuery, state: FSMContext, **data):
    # ... narx hisoblash va ko'rsatish ...
    # YANGI: journey event
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="PRICE_CALCULATED",
        user_id=callback.from_user.id,
        data={
            "area_m2": area,
            "design_name": design_name,
            "total_price": total_price,
            "discount_percent": discount,
        },
        source_handler="pricing.py",
    )))
```

Shuningdek `apps/bot/handlers/private/ai_pricing_helpers.py` da:
```python
# _show_price_upsell() da narx ko'rsatilgandan keyin:
async def _show_price_upsell(message, state, area, district=None, design=None):
    # ... narx hisoblash va ko'rsatish ...
    # YANGI: journey event
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="PRICE_CALCULATED",
        user_id=message.from_user.id,
        data={"area_m2": area, "design_name": design, "total_price": total},
        source_handler="ai_pricing_helpers.py",
    )))
```

---

### 2.6. CLICKED_ORDER

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `CLICKED_ORDER` |
| **Qachon trigger bo'ladi** | Buyurtma tugma bosilganda — `apps/bot/handlers/private/order.py` da `BTN_ORDER` / `/order` command yoki after_quote_keyboard dagi "Buyurtma berish" tugmasi. Shuningdek `ai_support.py` da `_is_measurement_request()` orqali |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `entry_point` ("main_menu" / "after_quote" / "ai_chat" / "package") |
| **Keyingi agent action** | Journey state = ORDERING ga set. **Barcha pending follow-up taymerlar bekor qilinadi** (buyurtma boshlangan — to'sqinlik qilmaslik kerak). Agar 10 daqiqa ichida form to'ldirilmasa — ORDER_FORM_ABANDONED trigger bo'ladi |
| **Redis key** | `journey:state:{user_id}` — ORDERING. Pending follow-up'larni cancel qilish: `agent:fu:catalog:{user_id}` DELETE, `agent:fu:price:{user_id}` DELETE |

**Handler fayl**: `apps/bot/handlers/private/order.py`
```python
# Order entry handler da:
@router.message(F.text == BTN_ORDER)
@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext, **data):
    # ... mavjud kod ...
    # YANGI: journey event (follow-up'larni bekor qiladi)
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="CLICKED_ORDER",
        user_id=message.from_user.id,
        data={"entry_point": "main_menu"},
        source_handler="order.py",
    )))
```

---

### 2.7. ORDER_FORM_STARTED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `ORDER_FORM_STARTED` |
| **Qachon trigger bo'ladi** | Buyurtma FSM ning birinchi qadami boshlanganda — `apps/bot/handlers/private/order.py` da `OrderStates.waiting_for_name` ga kirish. Foydalanuvchi ismini yozganda |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `form_step` ("waiting_for_name" — birinchi qadam) |
| **Keyingi agent action** | Agent memory update: `order_form_progress.started_at = now`. 10 daqiqalik inactivity timer boshlash |
| **Redis key** | `agent:fu:order_abandon:{user_id}` — 10 daqiqalik TTL. Har bir form qadam o'tishda reset (EXPIRE) qilinadi |

**Handler fayl**: `apps/bot/handlers/private/order.py`
```python
# OrderStates.waiting_for_name handler da (birinchi step):
async def handle_order_name(message: Message, state: FSMContext, **data):
    # ... mavjud kod ...
    # YANGI: journey event
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="ORDER_FORM_STARTED",
        user_id=message.from_user.id,
        data={"form_step": "waiting_for_name"},
        source_handler="order.py",
    )))
```

---

### 2.8. ORDER_FORM_ABANDONED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `ORDER_FORM_ABANDONED` |
| **Qachon trigger bo'ladi** | Buyurtma formasida 10 daqiqa nofaollik — agent scheduler tomonidan detect qilinadi. FSM state hali `OrderStates.*` da ekan (foydalanuvchi formadan chiqmagan) lekin 10 daqiqa hech narsa yozmagan |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `last_step` (masalan: "waiting_for_district"), `collected_data` (to'ldirilgan maydonlar: name, phone, etc.), `remaining_steps` (qancha qadam qolgan) |
| **Keyingi agent action** | Abandoned order follow-up yuborish: "Buyurtmangiz yarim qoldi! Davom etasizmi?" + [Davom] [Paketlar] [Bekor] tugmalari. Admin eskalatsiya: "Mijoz buyurtma formani tashlab ketdi" alert |
| **Redis key** | `agent:fu:order_abandon:{user_id}` — 10 daqiqalik TTL expired bo'lganda trigger. `agent:fu:order_abandon_sent:{user_id}` — 6h TTL, NX (1 marta yuborish) |

**Trigger mexanizmi**: Bu event handler ichida emas, balki **scheduler** tomonidan detect qilinadi:
```python
# apps/scheduler/jobs/agent_followup_jobs.py
async def check_abandoned_orders():
    """Every 60s: check for users stuck in OrderStates for >10 min."""
    # 1. Redis'dan barcha OrderStates dagi user'larni tekshirish
    # 2. Oxirgi faollik 10+ daqiqa oldin bo'lsa — ORDER_FORM_ABANDONED emit
    # 3. Yoki: Celery delayed task orqali (order form entry da 10 min delay bilan schedule)
```

---

### 2.9. PHONE_SHARED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `PHONE_SHARED` |
| **Qachon trigger bo'ladi** | Telefon raqam yuborilganda — `apps/bot/handlers/private/ai_support.py` `handle_phone_contact()` yoki `handle_phone_input()`. Shuningdek `order.py` da telefon step, va `ai_support.py` `handle_ai_message()` da `extract_phone_from_text()` orqali passive detect |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `phone` (formatted: +998XXXXXXXXX), `method` ("contact_share" / "text_input" / "passive_detect") |
| **Keyingi agent action** | Agent memory: `phone_captured = true`. Lead score: +40 ball. Admin darhol xabar oladi (enriched card). Journey state = CONTACTED ga o'tish mumkin. **Barcha pending follow-up'lar to'xtatiladi** |
| **Redis key** | `ai:followup_state:{user_id}` — `lead_created = true` set qilinadi (mavjud mexanizm). `agent:fu:phone_reminder:{user_id}` DELETE (phone reminder bekor) |

**Handler fayl**: `apps/bot/handlers/private/ai_support.py`
```python
# _complete_phone_step() da (ai_support.py:554):
async def _complete_phone_step(message, state, phone):
    # ... mavjud kod ...
    # YANGI: journey event
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="PHONE_SHARED",
        user_id=message.from_user.id,
        data={"phone": phone, "method": "contact_share"},
        source_handler="ai_support.py",
    )))
```

---

### 2.10. LOCATION_SHARED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `LOCATION_SHARED` |
| **Qachon trigger bo'ladi** | Lokatsiya yuborilganda — `apps/bot/handlers/private/order.py` da location step yoki `apps/bot/handlers/private/lead_capture.py` da lokatsiya qabuli |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `latitude`, `longitude` |
| **Keyingi agent action** | Agent memory update: lokatsiya saqlash. Google Maps link bilan admin notification. Yuqori niyat signali — lead scoring'da +5 ball |
| **Redis key** | Alohida dedup kerak emas |

**Handler fayl**: `apps/bot/handlers/private/order.py` (location handler)

---

### 2.11. IMAGE_SENT

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `IMAGE_SENT` |
| **Qachon trigger bo'ladi** | Foydalanuvchi shaxsiy chatda rasm yuborganda — `apps/bot/handlers/private/ai_support.py` `handle_photo_received()` (photo funnel), yoki default_state da photo message handler |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `file_id` (Telegram file ID), `chat_type` ("private") |
| **Keyingi agent action** | **DARHOL admin alert** — "Mijoz xona rasmini yubordi — tezda ko'ring!". URGENT belgi. Agent memory: `has_sent_photo = true`. Photo funnel boshlash (mavjud mexanizm: waiting_photo -> waiting_room -> waiting_area_photo) |
| **Redis key** | Dedup kerak emas — har bir rasm muhim |

**Handler fayl**: `apps/bot/handlers/private/ai_support.py`
```python
# handle_photo_received() da (ai_support.py:707):
@router.message(StateFilter(AiSupportStates.waiting_photo), F.photo)
async def handle_photo_received(message: Message, state: FSMContext, **data):
    # ... mavjud kod ...
    # YANGI: journey event + immediate admin alert
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="IMAGE_SENT",
        user_id=message.from_user.id,
        data={"file_id": message.photo[-1].file_id},
        source_handler="ai_support.py",
    )))
```

---

### 2.12. OPERATOR_REQUESTED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `OPERATOR_REQUESTED` |
| **Qachon trigger bo'ladi** | Operator tugma bosilganda — `apps/bot/handlers/private/operator.py` `BTN_OPERATOR`, `start_operator_flow()`. Shuningdek pricing.py after_quote keyboard dagi "Operator" tugma, va CTA callback'lardagi operator tugma |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `entry_point` ("main_menu" / "after_quote" / "cta_button" / "ai_chat") |
| **Keyingi agent action** | Admin eskalatsiya: enriched card bilan admin guruhga xabar. **Barcha follow-up'lar to'xtatiladi** — inson operator olib boradi. Journey state = CONTACTED. Agent memory: `stop_follow_ups = true`, `stop_reason = "operator_requested"` |
| **Redis key** | `agent:fu:daily:{user_id}` — barcha pending follow-up'lar cancel. Barcha `agent:fu:*:{user_id}` key'lar DELETE |

**Handler fayl**: `apps/bot/handlers/private/operator.py`
```python
# start_operator_flow() da:
async def start_operator_flow(message: Message, state: FSMContext):
    # ... mavjud kod ...
    # YANGI: journey event (barcha follow-up'larni to'xtatadi)
    asyncio.create_task(journey_event_service.emit(JourneyEvent(
        event_type="OPERATOR_REQUESTED",
        user_id=message.from_user.id,
        data={"entry_point": "main_menu"},
        source_handler="operator.py",
    )))
```

---

### 2.13. ADMIN_NOTIFIED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `ADMIN_NOTIFIED` |
| **Qachon trigger bo'ladi** | Admin guruhga lead notification yuborilganda — `core/services/lead_notification_service.py` `notify_new_lead()`, `notify_hot_lead()`. Va `apps/bot/handlers/private/ai_notifications.py` `_notify_ai_lead_collected()` |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `admin_group_id`, `notification_type` ("new_lead" / "hot_lead" / "ai_collected" / "journey_escalation") |
| **Keyingi agent action** | Log notification. Admin response kuzatish (agar admin 1 soat ichida harakatlanmasa — qayta eslatma) |
| **Redis key** | Mavjud: `lead:{lead_id}:card_sent` — 5 min dedup (CacheTTL.LEAD_CARD_SENT) |

---

### 2.14. DEAL_CLOSED

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `DEAL_CLOSED` |
| **Qachon trigger bo'ladi** | Pipeline stage DEAL ga o'tganda — `apps/bot/handlers/callbacks/kanban_callbacks.py` `kanban:move` callback, yoki `apps/bot/handlers/admin/lead_status.py` `lead:{id}:status:deal` callback, yoki `core/services/pipeline_service.py` `move_stage()` |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `lead_id`, `pipeline_stage` ("DEAL") |
| **Keyingi agent action** | **Terminal state**: journey state = CONVERTED. **Barcha follow-up'lar darhol to'xtatiladi**. `next_follow_up_at = NULL` set qilinadi. Agent memory: `stop_follow_ups = true`, `stop_reason = "deal_closed"` |
| **Redis key** | Barcha `agent:fu:*:{user_id}` key'lar DELETE |

---

### 2.15. LOST_LEAD

| Maydon | Qiymat |
|--------|--------|
| **Event nomi** | `LOST_LEAD` |
| **Qachon trigger bo'ladi** | Pipeline stage LOST ga o'tganda — `apps/bot/handlers/callbacks/kanban_callbacks.py` `kanban:move`, yoki `apps/bot/handlers/callbacks/pipeline_callbacks.py` lost flow, yoki `apps/bot/handlers/admin/lead_status.py` `lead:{id}:status:lost` callback |
| **Qanday data saqlanadi** | `user_id`, `timestamp`, `lead_id`, `lost_reason` ("price" / "competitor" / "no_response" / "not_interested" / "other") |
| **Keyingi agent action** | **Terminal state**: journey state = LOST. **Barcha follow-up'lar darhol to'xtatiladi**. Agent memory: `stop_follow_ups = true`, `stop_reason = "lead_lost"` |
| **Redis key** | Barcha `agent:fu:*:{user_id}` key'lar DELETE |

---

## 3. Journey State Machine Diagrammasi

```
                        ┌──────────────────────────────────────────┐
                        │           STATE MACHINE                   │
                        │                                          │
                        │  ┌──────┐                                │
           /start ─────►│  │ IDLE │                                │
                        │  └──┬───┘                                │
                        │     │                                    │
                        │     │ OPENED_CATALOG / VIEWED_ITEM       │
                        │     │ (BTN_CATALOG / /catalog)           │
                        │     v                                    │
                        │  ┌──────────┐                            │
                        │  │ BROWSING │◄────────────────┐          │
                        │  └────┬─────┘                 │          │
                        │       │                       │          │
                        │       │ USED_PRICE /           │          │
                        │       │ PRICE_CALCULATED       │ timeout  │
                        │       v                       │ (abandon)│
                        │  ┌─────────────┐              │          │
                        │  │ CALCULATING │              │          │
                        │  └──────┬──────┘              │          │
                        │         │                     │          │
                        │         │ CLICKED_ORDER /      │          │
                        │         │ ORDER_FORM_STARTED   │          │
                        │         v                     │          │
                        │  ┌──────────┐                 │          │
                        │  │ ORDERING │─────────────────┘          │
                        │  └────┬─────┘                            │
                        │       │                                  │
                        │       │ PHONE_SHARED /                    │
                        │       │ OPERATOR_REQUESTED               │
                        │       v                                  │
                        │  ┌───────────┐                           │
                        │  │ CONTACTED │                           │
                        │  └─────┬─────┘                           │
                        │        │                                 │
                        │   ┌────┴────┐                            │
                        │   │         │                            │
                        │   v         v                            │
                        │ ┌─────────┐ ┌──────┐                    │
                        │ │CONVERTED│ │ LOST │  ◄── terminal       │
                        │ └─────────┘ └──────┘      states        │
                        │                                          │
                        └──────────────────────────────────────────┘

  OPERATOR_REQUESTED yoki PHONE_SHARED har qanday state'dan
  CONTACTED ga o'tkazadi (bypass).

  DEAL_CLOSED har qanday state'dan CONVERTED ga o'tkazadi.
  LOST_LEAD har qanday state'dan LOST ga o'tkazadi.
```

---

## 4. Transition Qoidalari (Batafsil)

### Normal O'tishlar (Linear Flow)

```python
TRANSITIONS: dict[JourneyState, dict[str, JourneyState]] = {
    JourneyState.IDLE: {
        "STARTED_BOT": JourneyState.IDLE,       # state saqlanadi
        "OPENED_CATALOG": JourneyState.BROWSING,
        "USED_PRICE_CALCULATOR": JourneyState.CALCULATING,
        "CLICKED_ORDER": JourneyState.ORDERING,
    },
    JourneyState.BROWSING: {
        "OPENED_CATALOG": JourneyState.BROWSING,        # timer reset
        "VIEWED_CATALOG_ITEM": JourneyState.BROWSING,   # timer reset
        "USED_PRICE_CALCULATOR": JourneyState.CALCULATING,
        "CLICKED_ORDER": JourneyState.ORDERING,
    },
    JourneyState.CALCULATING: {
        "PRICE_CALCULATED": JourneyState.CALCULATING,   # timer start
        "CLICKED_ORDER": JourneyState.ORDERING,
        "OPENED_CATALOG": JourneyState.BROWSING,        # qayta katalogga
    },
    JourneyState.ORDERING: {
        "ORDER_FORM_STARTED": JourneyState.ORDERING,    # timer start
        "ORDER_FORM_ABANDONED": JourneyState.BROWSING,  # timeout -> back
    },
    JourneyState.CONTACTED: {
        # Terminal ga yaqin — faqat admin actions
    },
}
```

### Global O'tishlar (Har Qanday State'dan)

```python
GLOBAL_TRANSITIONS: dict[str, JourneyState] = {
    "PHONE_SHARED": JourneyState.CONTACTED,
    "OPERATOR_REQUESTED": JourneyState.CONTACTED,
    "DEAL_CLOSED": JourneyState.CONVERTED,
    "LOST_LEAD": JourneyState.LOST,
}
```

### O'tish Qoidalari

1. **Normal o'tish**: faqat `TRANSITIONS[current_state][event_type]` da aniqlangan bo'lsa
2. **Global o'tish**: `GLOBAL_TRANSITIONS[event_type]` har doim ishlaydi (current state muhim emas)
3. **Terminal state**: `CONVERTED` va `LOST` dan boshqa state'ga o'tish mumkin emas (ignore all events)
4. **Timer reset**: BROWSING va CALCULATING da takroriy eventlar timer'ni qayta boshlaydi
5. **Side effects**: har bir o'tish follow-up scheduler va agent memory ni yangilaydi

---

## 5. Event -> Handler Mapping (Mavjud Fayllar)

| Event | Primary Handler | Secondary Handlers |
|-------|----------------|-------------------|
| `STARTED_BOT` | `support.py` cmd_start() | — |
| `OPENED_CATALOG` | `catalog.py` cmd_catalog() | `ai_support.py` (_is_catalog_request) |
| `VIEWED_CATALOG_ITEM` | `catalog.py` design selection handler | — |
| `USED_PRICE_CALCULATOR` | `pricing.py` start_pricing_flow() | `ai_support.py` (_is_price_query), `ai_support.py` cb_start_price() |
| `PRICE_CALCULATED` | `pricing.py` design callback | `ai_pricing_helpers.py` _show_price_upsell() |
| `CLICKED_ORDER` | `order.py` cmd_order() | `pricing.py` after_quote "Buyurtma" button, `packages.py` package order |
| `ORDER_FORM_STARTED` | `order.py` first FSM step handler | `lead_capture.py` start_lead_capture() |
| `ORDER_FORM_ABANDONED` | *Scheduler-detected* | `agent_followup_jobs.py` check_abandoned_orders() |
| `PHONE_SHARED` | `ai_support.py` handle_phone_contact/input() | `order.py` phone step, `lead_capture.py` phone step |
| `LOCATION_SHARED` | `order.py` location step | `lead_capture.py` location handler |
| `IMAGE_SENT` | `ai_support.py` handle_photo_received() | — |
| `OPERATOR_REQUESTED` | `operator.py` start_operator_flow() | `pricing.py` after_quote "Operator", CTA callbacks |
| `ADMIN_NOTIFIED` | `lead_notification_service.py` | `ai_notifications.py` |
| `DEAL_CLOSED` | `kanban_callbacks.py` kanban:move | `lead_status.py` lead:status:deal, `pipeline_service.py` |
| `LOST_LEAD` | `kanban_callbacks.py` kanban:move | `pipeline_callbacks.py` lost flow, `lead_status.py` lead:status:lost |

---

## 6. Journey Events PostgreSQL Jadvali

```sql
CREATE TABLE journey_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    data JSONB DEFAULT '{}',
    source_handler VARCHAR(50),
    journey_state_before VARCHAR(20),
    journey_state_after VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tez so'rovlar uchun indekslar
CREATE INDEX ix_je_user_created ON journey_events(user_id, created_at DESC);
CREATE INDEX ix_je_type_created ON journey_events(event_type, created_at DESC);
CREATE INDEX ix_je_user_type ON journey_events(user_id, event_type);

-- 90 kundan eski eventlarni tozalash uchun (pg_cron yoki manual)
-- DELETE FROM journey_events WHERE created_at < NOW() - INTERVAL '90 days';
```

---

## 7. Redis Key Map (Barcha Journey-Related Key'lar)

```python
# Journey state (per-user)
CacheKeys.journey_state(user_id)           # f"journey:state:{user_id}"
CacheTTL.JOURNEY_STATE = 2_592_000         # 30 kun

# Follow-up cooldowns (per-type, per-user)
CacheKeys.agent_fu_cooldown(user_id, type) # f"agent:fu:{type}:{user_id}"
# TTL: type-specific (see Follow-up Engine doc)

# Daily follow-up counter (per-user)
CacheKeys.agent_fu_daily(user_id)          # f"agent:fu:daily:{user_id}"
CacheTTL.AGENT_FU_DAILY = 90_000           # 25h

# Order form abandonment tracker
CacheKeys.agent_fu_order_track(user_id)    # f"agent:fu:order_track:{user_id}"
CacheTTL.AGENT_FU_ORDER_TRACK = 660        # 11 min (10 min + 1 min grace)

# Global last follow-up timestamp (minimum gap enforcement)
CacheKeys.agent_fu_last(user_id)           # f"agent:fu:last:{user_id}"
CacheTTL.AGENT_FU_LAST = 3_600             # 1h min gap

# Per-event dedup (one follow-up per trigger event)
CacheKeys.agent_fu_event(event_id)         # f"agent:fu:event:{event_id}"
CacheTTL.AGENT_FU_EVENT = 86_400           # 24h
```

---

**Keyingi fayl**: [03_FOLLOW_UP_ENGINE.md](./03_FOLLOW_UP_ENGINE.md) — to'liq follow-up engine hujjati
