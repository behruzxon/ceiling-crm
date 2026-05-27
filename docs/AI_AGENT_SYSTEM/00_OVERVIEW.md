# Vashpotolok AI Agent System — Umumiy Ko'rinish

## 1. Maqsad

Vashpotolok AI Agent — bu oddiy "savol-javob" botdan tubdan farq qiladigan **proaktiv savdo agenti**. Agent har bir mijozning harakatlarini real vaqtda kuzatadi, niyatini aniqlaydi va eng to'g'ri momentda to'g'ri xabarni yuborib, mijozni buyurtmaga olib boradi.

Hozirgi bot tizimi reaktiv ishlaydi: mijoz yozsa — javob beradi, yozmasa — jim turadi. AI Agent esa **proaktiv** ishlaydi: mijoz katalogni ochib, 10 daqiqa sukut saqlasa — agent o'zi murojaat qiladi. Narx hisoblab, buyurtma bermasdan ketsa — agent eslatadi. Buyurtma formasini to'ldirib yarimta tashlab ketsa — agent davom etishga undaydi.

## 2. Bot Nimani Kuzatadi

Agent quyidagi **mijoz harakatlarini** (customer events) kuzatadi:

| Harakat | Qaerda sodir bo'ladi | Nima uchun muhim |
|---------|---------------------|-----------------|
| Katalogni ochish | `apps/bot/handlers/private/catalog.py` — BTN_CATALOG / /catalog | Mijoz dizaynlarga qiziqyapti |
| Narx kalkulyator | `apps/bot/handlers/private/pricing.py` — BTN_PRICE / /price | Sotib olish niyati bor |
| Buyurtma boshlash | `apps/bot/handlers/private/order.py` — BTN_ORDER / /order | Yuqori niyat — buyurtma bermoqchi |
| AI suhbat | `apps/bot/handlers/private/ai_support.py` — erkin yozma | Maslahat yoki e'tiroz bildiryapti |
| Telefon ulashish | `ai_support.py` — F.contact yoki matn telefoni | Juda yuqori niyat |
| Operator so'rash | `apps/bot/handlers/private/operator.py` — BTN_OPERATOR | Jonli yordam kerak |
| Rasm yuborish | `ai_support.py` — F.photo | Jiddiy qiziqish — xona rasmi |
| Paketlar ko'rish | `apps/bot/handlers/private/packages.py` — BTN_PACKAGES | Tayyor yechimga qiziqyapti |
| Manzil/tuman aytish | `ai_support.py` — district detection | O'lchov uchun tayyor |

## 3. Agent Nimani Hal Qiladi

### A) Yarim Qolgan Harakatlar (Abandoned Actions)
- **Katalog tashlab ketish**: Mijoz katalogni ochdi, 10 daqiqa hech narsa qilmadi — agent "Qaysi model yoqdi?" deb so'raydi
- **Narx tashlab ketish**: Narx hisoblab, buyurtma bermadi — agent narxni eslatib, CTA yuboradi
- **Buyurtma tashlab ketish**: Buyurtma formasini boshladi, yarimta tashlab ketdi — agent "Davom etasizmi?" deb so'raydi

### B) Sukut Saqlovchi Mijozlar (Silent Users)
- 24 soatdan keyin yumshoq eslatma
- 72 soatdan keyin oxirgi taklif
- 7 kundan keyin LOST belgisi

### C) Narx E'tirozlari (Price Objections)
- "Qimmat" desa — arzonroq variant taklif qilish
- "O'ylab ko'raman" desa — bepul o'lchov taklifi
- "Raqobatchida arzonroq" desa — sifat ustunligini tushuntirish

### D) To'g'ri Vaqtni Tanlash (Smart Timing)
- Ish vaqtida (09:00-21:00 Toshkent) yuborish
- HOT leadga 10-20 daqiqada javob
- COLD leadga 24 soatda javob
- Spam bo'lmasligi uchun kuniga max 3 ta follow-up

## 4. Qanday Qilib Mijozni Savdoga Olib Boradi

```
1. Mijoz /start bosadi
   └─► Agent: xush kelibsiz + asosiy menyu ko'rsatadi
       └─► Memory: user_id, timestamp, source saqlaydi

2. Mijoz katalogni ochadi
   └─► Agent: state = BROWSING, 10 daqiqalik taymer boshlanadi
       └─► 10 daqiqa javob yo'q?
           └─► "Qaysi model yoqdi? Kvadratni yozsangiz narxni hisoblab beraman"

3. Mijoz narx kalkulyatordan foydalanadi
   └─► Agent: state = CALCULATING, 10 daqiqalik taymer boshlanadi
       └─► Narx chiqdi, buyurtma bermadi?
           └─► "{design} uchun {area}m2 narxi — {price}. Buyurtma berasizmi?"
               └─► [Buyurtma] [Operator] tugmalari bilan

4. Mijoz buyurtma formani boshlaydi
   └─► Agent: state = ORDERING, barcha follow-up taymerlar bekor bo'ladi
       └─► 10 daqiqa ichida davom etmadi?
           └─► "Buyurtmangiz yarim qoldi! Davom etasizmi?"
               └─► [Davom] [Paketlar] [Bekor] tugmalari bilan

5. Mijoz telefon raqamini yuboradi
   └─► Agent: phone_captured = true, admin guruhiga darhol xabar
       └─► "Rahmat! Mutaxassisimiz tez orada siz bilan bog'lanadi"

6. Admin bog'lanadi / buyurtma rasmiylashadi
   └─► Agent: state = CONTACTED yoki CONVERTED
       └─► Barcha follow-uplar to'xtatiladi
```

## 5. Oddiy Bot vs AI Agent Farqi

| Xususiyat | Oddiy Bot | AI Agent |
|-----------|-----------|----------|
| Savollarga javob | Ha | Ha |
| Mijoz ketsa — eslatma | Yo'q | Ha, 10 daqiqada |
| Buyurtma tashlab ketsa | Yo'q | "Davom etasizmi?" xabari |
| Narx oldi, ketdi | Yo'q | Narxni eslatib, CTA yuboradi |
| Katalog ochdi, ketdi | Yo'q | "Qaysi model yoqdi?" |
| E'tirozga javob | Shablon javob | Negotiation engine |
| Lead scoring | Yo'q | 0-100 ball, HOT/WARM/COLD |
| Xaridor turi aniqlash | Yo'q | 4 ta tur (price/quality/fast/research) |
| Deal probability | Yo'q | 0-100% ehtimollik |
| Admin eslatma | Qo'lda | Avtomatik, enriched card |
| Follow-up timing | Yo'q | Business hours + lead temp based |
| Spam himoya | Yo'q | Max 3/kuniga, cooldown, stop conditions |
| Memory | Yo'q | 30 kunlik per-user memory |

## 6. Kutilayotgan Biznes Ta'sir (Expected Business Impact)

### Konversiya Oshishi: +20-30%
- Hozir: narx olgan mijozlarning ~60% buyurtma bermay ketadi
- Agent bilan: 10 daqiqalik follow-up bu raqamni 30-40% ga tushiradi
- Asosiy sabab: mijozlar unutadi yoki diqqat tarqaladi — agent eslatadi

### Javob Vaqti Qisqarishi: -50%
- Hozir: admin qo'lda lead kartani ko'rib, qo'ng'iroq qiladi (1-4 soat)
- Agent bilan: HOT lead kelishi bilan 10-20 daqiqada admin alert + suggested action
- Natija: HOT leadlar 2x tezroq qayta ishlanadi

### Lead Yo'qotish Kamayishi: -70%
- Hozir: katalog ochgan, narx olgan lekin buyurtma bermagan mijozlar "yo'qoladi"
- Agent bilan: har bir harakat kuzatiladi, follow-up yuboriladi
- Natija: 10 ta yo'qolgan leaddan 7 tasi qaytariladi

### Operatsion Samaradorlik: +40%
- Hozir: admin barcha leadlarni qo'lda boshqaradi
- Agent bilan: faqat "tayyor" leadlar adminga keladi (filtrlangan, enriched)
- Natija: admin bir kunda 40% ko'proq leadni qayta ishlaydi

## 7. Hozirgi Holat: Mavjud Tizim (Current State)

### 42+ Servislar (`core/services/`)

| Servis | Fayl | Vazifa |
|--------|------|--------|
| FollowupService | `followup_service.py` | Brain-driven admin follow-up reminders (60s interval) |
| FollowupBrainService | `followup_brain_service.py` | 6 ta follow-up turi, smart delay, progressive backoff |
| LeadNotificationService | `lead_notification_service.py` | Admin guruhga lead card (Kanban buttons bilan) |
| PricingService | `pricing_service.py` | Per-design narx hisoblash, addon, discount |
| LeadService | `lead_service.py` | Lead CRUD + pipeline integration |
| LeadIntelligenceService | `lead_intelligence_service.py` | 4 xaridor turi: price_sensitive, quality, fast, research |
| NegotiationEngineService | `negotiation_engine_service.py` | 5 taktika: value_reframe, cheaper_alt, urgency_close... |
| DealCloserService | `deal_closer_service.py` | AI-powered closing readiness assessment |
| RevenuePredictorService | `revenue_predictor_service.py` | Lead daromad bashorati (min/max/best) |
| SignalVectorService | `signal_vector_service.py` | Lead signallarini vektor formatiga o'girish |
| ConversationIntelligenceService | `conversation_intelligence_service.py` | Suhbat health score, cooling detection |
| AutoSalesService | `auto_sales_service.py` | Template auto-reply + escalation logic |
| AiAutoCloserService | `ai_auto_closer_service.py` | Closing readiness alerts |
| AiOrchestratorService | `ai_orchestrator_service.py` | AI tizimlar koordinatsiyasi |
| AiSalesBrainService | `ai_sales_brain_service.py` | Markaziy AI sales strategiya |
| OutcomeResolverService | `outcome_resolver_service.py` | Tactic outcome tracking |
| TacticPerformanceService | `tactic_performance_service.py` | Tactic performance analytics |
| AdaptiveWeightsService | `adaptive_weights_service.py` | Outcome-based tactic weight tuning |
| ClosingReadinessService | `closing_readiness_service.py` | Lead closing tayyor-tayyor emas baholash |
| DealRadarService | `deal_radar_service.py` | Pipeline opportunity detection |
| NextBestActionService | `next_best_action_service.py` | Admin uchun eng yaxshi keyingi harakat tavsiyasi |
| SalesAnalyticsService | `sales_analytics_service.py` | Sales performance analytics |

### Mavjud AI Engine (ai_support.py + 8 sibling module)

- **ai_support.py** (1241 qator) — asosiy router + wiring
- **ai_states.py** — FSM states (7 ta state), keyboards, text constants
- **ai_detection.py** — Intent/trigger detection, area/district parsing
- **ai_memory.py** — Redis per-user memory (30 kun), stats counters
- **ai_scoring.py** — Lead scoring (0-100), objection detection (price/delay/trust)
- **ai_openai.py** — OpenAI GPT-4o integration, conversation persistence
- **ai_notifications.py** — Admin notification orchestration (5 layer: scoring + probability + buyer + revenue + negotiation)
- **ai_followups.py** — Delayed follow-ups: catalog (5-10 min), AI interaction (10 min + 60 min)
- **ai_pricing_helpers.py** — Price display, combo confirmation

### Mavjud Follow-up Tizimi

- **Brain-driven**: `FollowupBrainService` 6 ta follow-up turi bilan
- **60 soniyada** scheduler tekshiradi (`check_due_followups`)
- **15 daqiqada** nofaol leadlar tekshiriladi (`check_inactive_leads`)
- **10 daqiqada** HOT lead inactivity alert (`check_hot_lead_inactivity`)
- **Max 5 ta** follow-up per lead (hard cap)
- **Business hours** aware (09:00-21:00 Toshkent, dam olish kunlari chetlangan)

### Mavjud Redis Cache Keys (`infrastructure/cache/keys.py`)

- `ai:memory:{user_id}` — per-user AI memory (30 kun TTL)
- `ai:score:{user_id}` — lead score 0-100 (30 kun TTL)
- `ai:followup_state:{user_id}` — follow-up state JSON (24 soat TTL)
- `ai:last_interaction:{user_id}` — oxirgi faollik timestamp (24 soat TTL)
- `madina:followup_nonce:{user_id}` — nonce for follow-up dedup (2 soat TTL)
- `madina:catalog_followup:{user_id}` — catalog follow-up dedup (24 soat TTL)
- `closer:last:{user_id}` — sales closer cooldown (10 daqiqa TTL)

### Mavjud Scheduler Jobs (`apps/scheduler/`)

| Job | Interval | Fayl |
|-----|----------|------|
| check_due_followups | 60s | `followup_jobs.py` |
| check_inactive_leads | 15 min | `followup_jobs.py` |
| check_hot_lead_inactivity | 10 min | `followup_jobs.py` |
| run_auto_sales_monitor | 10 min | `auto_sales_jobs.py` |
| run_conversation_intelligence | 10 min | `conversation_intelligence_jobs.py` |
| run_sales_autopilot | 10 min | `sales_autopilot_jobs.py` |
| check_closing_readiness | 10 min | `closing_jobs.py` |
| resolve_outcomes | 15 min | `outcome_resolver_jobs.py` |
| warm_analytics_cache | 30 min | `analytics_jobs.py` |
| warm_price_cache | 30 min | `cache_jobs.py` |

## 8. Yangilanish Nimani Qo'shadi (What This Upgrade Adds)

### A) Journey Tracking Layer (Yangi)
- **JourneyEventService** (`core/services/journey_event_service.py`) — har bir mijoz harakatini event sifatida qayd qiladi
- **customer_journey_states** jadvali (PostgreSQL) — journey state persistensiyasi
- Journey state machine: `IDLE -> BROWSING -> CALCULATING -> ORDERING -> CONTACTED -> CONVERTED | LOST`
- Mavjud handler'larga event emit qo'shish (catalog.py, pricing.py, order.py, ai_support.py, packages.py)

### B) 10-Daqiqalik Follow-up Engine (Kengaytirilgan)
- Mavjud `_catalog_followup_task` va `_ai_followup_task` asosida kengaytirish
- 7 ta follow-up qoidasi: Catalog, Price, Abandoned Order, Phone Reminder, 24H Soft, 72H Final, Image Response
- Event-driven trigger (hozirgi `asyncio.sleep` o'rniga APScheduler + Celery integratsiya)
- Anti-spam: max 3 follow-up per user per day, event-type cooldown

### C) Structured Agent Memory (Kengaytirilgan)
- Mavjud `CacheKeys.ai_memory` kengaytirish: journey_state, last_event, intent_history, follow_up_history qo'shish
- **AgentMemoryService** (`core/services/agent_memory_service.py`) — memory CRUD + merge logic
- PostgreSQL backup: `agent_memory` jadvali (Redis crash bo'lsa memory yo'qolmasligi uchun)

### D) Event-Driven Triggers (Yangi)
- Mavjud handler'larga hook qo'shish (har bir muhim harakat event emit qiladi)
- Event -> Follow-up Scheduler -> Message Composer -> Send pipeline
- Mavjud `core/events/bus.py` event bus bilan integratsiya

---

**Keyingi fayl**: [01_AGENT_ARCHITECTURE.md](./01_AGENT_ARCHITECTURE.md) — to'liq arxitektura
