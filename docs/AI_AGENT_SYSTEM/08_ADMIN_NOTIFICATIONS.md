# 08 — Admin Notifications (Admin Xabarnomalar Tizimi)

## 1. Umumiy Ko'rinish

Admin xabarnomalar tizimi **LeadNotificationService** orqali `BOT_ADMIN_GROUP_ID` guruhga yuboriladi. Har bir xabarnoma **enriched card** formatida — lead ma'lumotlari, AI scoring, journey context va inline tugmalar bilan.

Xabarnomalar **fire-and-forget** pattern bilan yuboriladi — asosiy tranzaksiyaga ta'sir qilmaydi. Bot o'z lifecycle'ini boshqaradi (`aiogram.Bot` instance yaratadi va yopadi).

### Texnik Infratuzilma

| Komponent | Fayl | Vazifa |
|-----------|------|--------|
| LeadNotificationService | `core/services/lead_notification_service.py` | Asosiy notification dispatcher |
| AI Notifications | `apps/bot/handlers/private/ai_notifications.py` | AI scoring + orchestrator integration |
| Lead Status Callbacks | `apps/bot/handlers/admin/lead_status.py` | Inline button callbacks (status update) |
| Kanban Callbacks | `apps/bot/handlers/callbacks/kanban_callbacks.py` | Kanban board inline buttons |
| FollowupService | `core/services/followup_service.py` | Follow-up reminder cards |

### Notification Target

```
BOT_ADMIN_GROUP_ID  (shared/config/settings.py)
  └── Telegram guruh yoki kanal
  └── Barcha admin xabarnomalar shu yerga yuboriladi
```

---

## 2. Notification Trigger Events

Admin quyidagi hodisalarda xabarnoma oladi:

| # | Hodisa | Trigger Manbasi | Ustuvorlik | Kutish |
|---|--------|-----------------|-----------|--------|
| 1 | Yangi lead (har qanday manba) | `lead_capture.py`, `packages.py` | HIGH | Darhol |
| 2 | Narx hisoblandi — buyurtma yo'q | `pricing.py` event + scheduler | MEDIUM | 10-15 min |
| 3 | Mijoz rasm yubordi | `ai_support.py` (F.photo handler) | URGENT | Darhol |
| 4 | Buyurtma formasi tashlab ketildi | `order.py` FSM timeout detection | HIGH | 10 min |
| 5 | 2x follow-up javobsiz | `followup_service.py` | MEDIUM | Auto |
| 6 | Operator so'raldi | `operator.py` / `support.py` | HIGH | Darhol |
| 7 | HOT lead aniqlandi (score >= 60) | `ai_scoring.py` threshold | HIGH | Darhol |
| 8 | Deal closing imkoniyati | `deal_closer_service.py` | HIGH | Darhol |
| 9 | Kunlik hisobot | `apps/scheduler/` daily job | LOW | Har kuni 21:00 |

### Trigger Flow

```
Handler harakat
  └── Event emit (service call / asyncio.create_task)
      └── AI Scoring pipeline
          ├── deal_probability
          ├── buyer_type
          ├── revenue_estimate
          ├── conversation_health
          └── negotiation_result
      └── LeadNotificationService.notify_*()
          └── Bot.send_message(admin_group_id, card, reply_markup=keyboard)
```

---

## 3. Notification Formatlari

### Format 1 — Yangi Lead Card (New Lead)

**Trigger**: `notify_new_lead(lead)` yoki `notify_ai_lead_collected(...)`
**Fayl**: `lead_notification_service.py` + `ai_notifications.py`

```
🆕 YANGI LEAD

👤 Ism: {first_name}
📞 Tel: +{phone}  ← clickable: tel:+998901234567
📱 TG: @{username} ← clickable
📍 Tuman: {district}

🔥 Status: HOT (score: 75)
🧠 Xaridor turi: Sifat xaridori
💰 Narx: 5,000,000 so'm (Gulli, 20m²)

📊 Journey:
  1. Katalog ko'rdi (14:30)
  2. Narx hisobladi (14:35)
  3. Buyurtma boshladi (14:40)

💡 Tavsiya: Darhol qo'ng'iroq qiling — mijoz tayyor!

[📞 Qo'ng'iroq] [📋 Lead] [🔄 Status]
```

**Inline Keyboard**:
```python
InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📌 Kanban'da ochish",
                          callback_data=f"kanban:lead:{lead_id}:new")],
    [InlineKeyboardButton(text="✅ Bog'landim",
                          callback_data=f"lead:{lead_id}:status:contacted"),
     InlineKeyboardButton(text="📅 O'lchov",
                          callback_data=f"lead:{lead_id}:status:measurement")],
    [InlineKeyboardButton(text="💰 Narx yuborildi",
                          callback_data=f"lead:{lead_id}:status:quoted"),
     InlineKeyboardButton(text="🧾 Zakaz",
                          callback_data=f"lead:{lead_id}:status:deal")],
    [InlineKeyboardButton(text="❌ LOST",
                          callback_data=f"lead:{lead_id}:status:lost")],
])
```

**Enriched Fields** (AI Orchestrator orqali):
- `deal_probability` — 0-100% ehtimollik + confidence level
- `buyer_profile` — xaridor turi (price_sensitive / quality / fast / research)
- `revenue_estimate` — min/max/best daromad bashorati (UZS)
- `conversation_health` — suhbat health score + cooling detection
- `followup_decision` — brain-driven keyingi follow-up tavsiyasi
- `negotiation_result` — qo'llanilgan taktika (agar e'tiroz bo'lsa)

---

### Format 2 — Buyurtma Tashlab Ketildi (Abandoned Order Alert)

**Trigger**: Buyurtma formasi 10 daqiqa davomida to'ldirilmasa
**Ustuvorlik**: HIGH — mijoz buyurtma berish niyatida edi

```
⚠️ BUYURTMA TASHLAB KETILDI

👤 {first_name} (@{username})
📞 {phone}
📍 {district}

Form holati:
✅ Ism: Ha
✅ Telefon: Ha
❌ Tuman: Yo'q (shu yerda to'xtadi)
❌ Potolok turi: —
❌ O'lcham: —

🕐 10 daqiqa oldin to'xtadi
🤖 Follow-up yuborildi: Ha

💡 Tavsiya: Telefonga qo'ng'iroq qiling

[📞 Qo'ng'iroq] [📋 Lead] [🔄 Davom ettirish]
```

**Callback Data Pattern**:
- `📞 Qo'ng'iroq` — `tel:+{phone}` URL button
- `📋 Lead` — `kanban:lead:{lead_id}:new`
- `🔄 Davom ettirish` — `lead:{lead_id}:status:contacted`

**Ma'lumot Manbasi**:
- FSM state dan qaysi field'lar to'ldirilganini aniqlash
- `lead_actions` jadvalidan oxirgi harakat vaqtini olish
- Follow-up yuborilgan-yuborilmaganini Redis dedup key'dan tekshirish

---

### Format 3 — Narx Hisoblandi, Buyurtma Yo'q (Price Calculated, No Order)

**Trigger**: Mijoz `PricingService` orqali narx hisobladi, 10-15 daqiqa ichida buyurtma bermadi
**Ustuvorlik**: MEDIUM — qiziqish bor, lekin qaror qilmagan

```
💰 NARX HISOBLANDI — BUYURTMA YO'Q

👤 {first_name} (@{username})
📐 O'lcham: {area}m²
🎨 Dizayn: {design}
💵 Narx: {price} so'm

🕐 15 daqiqa oldin hisobladi
🤖 Follow-up: Kutilmoqda (10 min)

[📞 Qo'ng'iroq] [📋 Lead]
```

**Kontekst Ma'lumotlari**:
- `area_m2` — FSM state yoki lead jadvalidan
- `design` — tanlangan potolok dizayn turi
- `price` — PricingService.calculate() natijasi (formatlanadi: `1,500,000 so'm`)
- Follow-up holati — scheduler'da pending yoki allaqachon yuborilgan

---

### Format 4 — Mijoz Rasm Yubordi (Image Received — URGENT)

**Trigger**: `ai_support.py` da F.photo handler — mijoz xona rasmini yubordi
**Ustuvorlik**: URGENT — bu jiddiy qiziqish belgisi

```
📸 MIJOZ RASM YUBORDI!

👤 {first_name} (@{username})
📞 {phone}
🔥 Status: {temperature}

Rasm: [forwarded photo]

💡 Bu jiddiy qiziqish belgisi — darhol javob bering!

[📞 Qo'ng'iroq] [📋 Lead]
```

**Texnik Eslatmalar**:
- Rasm `bot.forward_message()` yoki `bot.send_photo(file_id)` orqali forward qilinadi
- Agar telefon raqam mavjud bo'lsa, clickable `tel:` link sifatida ko'rsatiladi
- Temperature (HOT/WARM/COLD) AI scoring pipeline'dan olinadi
- Rasm yuborgan mijoz avtomatik +15 score oladi (jiddiy qiziqish signali)

---

### Format 5 — Follow-up Javobsiz (Follow-up No Response)

**Trigger**: `FollowupService.process_due_followups()` — ikki marta follow-up yuborildi, javob yo'q
**Ustuvorlik**: MEDIUM — mijoz sovumoqda, admin aralashuvi kerak

```
🔕 MIJOZ JAVOB BERMAYAPTI

👤 {first_name} (@{username})
📞 {phone}

Follow-up tarixi:
  1️⃣ Katalog follow-up (2 soat oldin) — ❌ javob yo'q
  2️⃣ Narx follow-up (1 soat oldin) — ❌ javob yo'q

🕐 Jami jimlik: 3 soat
🔥 Status: WARM → COLD ga o'tmoqda

💡 Tavsiya: Qo'ng'iroq yoki oxirgi taklif

[📞 Qo'ng'iroq] [🎁 Maxsus taklif] [❌ Lost]
```

**Callback Data**:
- `📞 Qo'ng'iroq` — `tel:+{phone}` URL button
- `🎁 Maxsus taklif` — `lead:{lead_id}:status:quoted` (maxsus narx taklifi yuborish)
- `❌ Lost` — `lead:{lead_id}:status:lost` (leadni LOST ga o'tkazish)

**Follow-up Tarixi Manbasi**:
- `lead_actions` jadvalidan `action_type = 'followup_sent'` yozuvlari
- `leads.follow_up_count` — jami follow-up soni
- `ai:followup_state:{user_id}` Redis key'dan follow-up holati

---

### Format 6 — Kunlik Hisobot (Daily Summary)

**Trigger**: Scheduler job — har kuni 21:00 Toshkent vaqtida
**Ustuvorlik**: LOW — informativ

```
📊 KUNLIK HISOBOT — {date}

👥 Yangi leadlar: {new_leads}
🔥 HOT: {hot_count} | 🟡 WARM: {warm_count} | ❄️ COLD: {cold_count}

📈 Pipeline:
  NEW: {new} → CONTACTED: {contacted} → MEASUREMENT: {measurement}
  QUOTE: {quote} → DEAL: {deal} ✅

🤖 AI follow-up:
  Yuborilgan: {sent} | Javob olgan: {replied} | Konversiya: {conversion}%

💡 Bugungi tavsiya: {ai_recommendation}
```

**Ma'lumot Manbalari**:
- `leads` jadvali — bugungi yangi leadlar, temperature breakdown
- `pipeline_stages` jadvali — har bir bosqichdagi lead soni (`get_counts_by_stage()`)
- `lead_actions` jadvali — follow-up sent/replied hisobi
- `ai_recommendation` — `NextBestActionService` dan umumiy tavsiya

---

## 4. Enriched Admin Card — AI Intelligence Stack

Har bir lead card quyidagi AI layer'lardan enriched bo'ladi:

### Layer 1: Lead Scoring (0-100)
```
🔥 Score: 75 (HOT)
```
**Manba**: `ai_scoring.py` — `_get_lead_score(user_id)`
**Threshold**: HOT >= 60, WARM >= 30, COLD < 30

### Layer 2: Deal Probability (0-100%)
```
📊 Ehtimol: 68% (medium)
```
**Manba**: `shared/utils/deal_probability.py` — `evaluate_deal_probability()`
**Signallar**: score * 0.4 + confidence * 20 + phone(+10) + area(+7) + district(+4) + closing(+8)

### Layer 3: Buyer Type
```
🧠 Xaridor: ⭐ Sifat xaridori (65%)
📞 Strategiya: Premium variantlarni ko'rsating
```
**Manba**: `core/services/lead_intelligence_service.py` — `analyze_buyer_type()`
**Turlar**: price_sensitive, quality_buyer, fast_buyer, research_buyer

### Layer 4: Revenue Estimate
```
💰 Daromad: 3,500,000 — 8,200,000 UZS
💵 Eng yaxshi: 5,800,000 UZS
📦 Upsell: yuqori — Premium tekstura + LED RGB
```
**Manba**: `core/services/revenue_predictor_service.py` — `predict_lead_revenue()`
**Hisoblash**: area_m2 * design_price_per_m2 + addon'lar

### Layer 5: Conversation Health
```
💬 Suhbat: 78% (healthy)
⚠️ Cooling: Yo'q
```
**Manba**: `core/services/conversation_intelligence_service.py` — `analyze_conversation()`

### Layer 6: Follow-up Brain Decision
```
📋 Keyingi: soft_reminder (45 daqiqada)
```
**Manba**: `core/services/followup_brain_service.py` — `decide_follow_up()`

### Layer 7: Negotiation Result (agar mavjud)
```
🤝 Taktika: value_reframe
💬 Javob: Premium materiallar uchun sifat kafolati...
```
**Manba**: `core/services/negotiation_engine_service.py` — `analyze_negotiation()`

---

## 5. Inline Keyboard — Callback Data Patterns

Admin card'dagi tugmalar quyidagi callback pattern'larni ishlatadi:

### Lead Status Update
```
lead:{lead_id}:status:{new_status}
```
**Handler**: `apps/bot/handlers/admin/lead_status.py` — regex `^lead:\d+:status:\w+$`
**Statuslar**: contacted, measurement, quoted, deal, lost
**Harakat**: `lead_status` ni yangilaydi, terminal status (deal/lost) da `next_follow_up_at` ni tozalaydi

### Kanban Navigation
```
kanban:lead:{lead_id}:{stage}       — lead detailga o'tish
kanban:stage:{stage}:{offset}       — stage lead listini ko'rish
kanban:move:{lead_id}:{new_stage}   — lead'ni boshqa stage'ga ko'chirish
kanban:assign:{lead_id}             — manager tayinlash
kanban:back                         — kanban overview'ga qaytish
```
**Handler**: `apps/bot/handlers/callbacks/kanban_callbacks.py`

### Phone Link (URL Button)
```python
InlineKeyboardButton(
    text="📞 Qo'ng'iroq",
    url=f"tel:+{phone}"  # Telegramda clickable tel: link
)
```

---

## 6. Anti-Spam va Deduplication

### Lead Card Deduplication
- **HOT lead**: `last_action == "hot_alert_sent"` tekshiruvi — bir xil lead uchun takroriy HOT alert yuborilmaydi
- **Method**: `notify_hot_lead()` `lead_actions` jadvalidan `last_action` ni tekshiradi

### Follow-up Notification Dedup
- **Redis NX key**: `madina:followup_nonce:{user_id}` (2 soat TTL)
- **Catalog follow-up**: `madina:catalog_followup:{user_id}` (24 soat TTL)
- **Closer cooldown**: `closer:last:{user_id}` (10 daqiqa TTL)

### Rate Limiting
- Kuniga max 5 ta follow-up per lead (`leads.follow_up_count` hard cap)
- Business hours only: 09:00-21:00 Toshkent vaqti
- Dam olish kunlari chetlangan

---

## 7. Error Handling

Barcha notification method'lari **never raise** pattern bilan ishlaydi:

```python
async def notify_new_lead(self, lead: Lead) -> None:
    try:
        bot = Bot(token=self._bot_token)
        try:
            await bot.send_message(self._admin_user_id, card, reply_markup=kb)
        finally:
            await bot.session.close()
    except Exception:
        log.warning("notify_new_lead_failed", lead_id=lead.id)
```

**Sabab**: Admin notification xatosi asosiy CRM flowga ta'sir qilmasligi kerak. Agar Telegram API 429 (rate limit) qaytarsa, xabar yo'qoladi lekin CRM ishlashda davom etadi.

---

## 8. Konfiguratsiya

### Environment Variables
```bash
BOT_TOKEN=...                    # Bot token (notification uchun Bot instance yaratadi)
BOT_ADMIN_GROUP_ID=...           # Admin guruh ID (notification target)
BOT_ADMIN_USER_ID=...            # Admin user ID (fallback DM target)
```

### Settings Access
```python
from shared.config import get_settings
settings = get_settings()
admin_group = settings.bot.admin_group_id
admin_user = settings.bot.admin_user_id
bot_token = settings.bot.token
```

---

## 9. Kengaytirish Yo'riqnomasi (Extension Guide)

Yangi notification turi qo'shish uchun:

### 1-Qadam: Service Method
`core/services/lead_notification_service.py` da yangi method:
```python
async def notify_custom_event(self, *, lead_id: int, context: dict) -> None:
    """Yangi notification turi. Never raises."""
    try:
        bot = Bot(token=self._bot_token)
        try:
            card = self._format_custom_card(context)
            kb = self._custom_keyboard(lead_id)
            await bot.send_message(self._admin_user_id, card,
                                   reply_markup=kb, parse_mode="HTML")
        finally:
            await bot.session.close()
    except Exception:
        log.warning("notify_custom_failed", lead_id=lead_id)
```

### 2-Qadam: Trigger Point
Handler yoki service'da fire-and-forget chaqirish:
```python
svc = get_lead_notification_service()
asyncio.create_task(svc.notify_custom_event(lead_id=lead.id, context={...}))
```

### 3-Qadam: Callback Handler (agar inline button kerak bo'lsa)
`apps/bot/handlers/admin/` yoki `callbacks/` da callback handler:
```python
@router.callback_query(F.data.regexp(r"^custom:\d+:action:\w+$"))
async def cb_custom_action(callback: CallbackQuery, db_session: AsyncSession):
    ...
```

---

**Oldingi fayl**: [07_...](./07_...) | **Keyingi fayl**: [09_IMPLEMENTATION_ROADMAP.md](./09_IMPLEMENTATION_ROADMAP.md)
