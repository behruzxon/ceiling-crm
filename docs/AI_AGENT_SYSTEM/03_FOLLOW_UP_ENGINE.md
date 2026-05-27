# Follow-up Engine — To'liq Hujjat

## 1. Asosiy 10-Daqiqalik Qoidalar

Har bir qoida uchun to'liq spetsifikatsiya: trigger, delay, condition, message, max count, cooldown, stop conditions, admin escalation, Redis key, scheduler integration.

---

### A) CATALOG FOLLOW-UP (10 daqiqa)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | `OPENED_CATALOG` yoki `VIEWED_CATALOG_ITEM` — foydalanuvchi katalogni ochdi yoki dizayn ko'rdi, lekin 10 daqiqa davomida boshqa harakat qilmadi |
| **Delay** | 10 daqiqa (600 soniya). Mavjud `_catalog_followup_task` 5-10 min random delay ishlatadi — yangi tizim aniq 10 min |
| **Condition (qachon yuborish)** | 1) Foydalanuvchi FSM state'da emas (na OrderStates, na PricingStates, na LeadCaptureStates). 2) Hali buyurtma bermagan. 3) Operator so'ramagan. 4) "kerak emas" demagan. 5) Business hours ichida (09:00-21:00 Toshkent) |
| **Condition (qachon yuborMASLIK)** | 1) Foydalanuvchi javob berdi (ai_last_interaction yangilandi). 2) Foydalanuvchi FSM state'ga kirdi (buyurtma yoki narx hisoblash boshladi). 3) Oxirgi 24 soatda allaqachon catalog_followup yuborilgan. 4) `stop_follow_ups = true` |
| **Message** | "Salom {name} 😊 Katalogdagi qaysi model sizga yoqdi? Xonangiz kvadratini yozsangiz, taxminiy narxni 1 daqiqada hisoblab beraman." |
| **Inline buttons** | Yo'q — oddiy matn, foydalanuvchi erkin javob yozadi |
| **Max yuborish** | 1 marta per 24 soat |
| **Cooldown** | 24 soat (CacheTTL: 86_400) |
| **Stop conditions** | 1) Foydalanuvchi javob berdi. 2) Buyurtma berdi. 3) "kerak emas" / "yo'q" / "boshlama" dedi. 4) Operator so'radi. 5) DEAL/LOST state'ga o'tdi |
| **Admin escalation** | YO'Q — past niyat, admin bezovta qilinmaydi |
| **Redis key (dedup)** | `agent:fu:catalog:{user_id}` — TTL 86_400 (24h), NX flag |
| **Redis key (cancel check)** | `ai:last_interaction:{user_id}` — agar follow-up schedule vaqtidan keyin yangilangan bo'lsa, cancel |
| **Scheduler integration** | **Celery delayed task**: `send_catalog_followup.apply_async(args=[user_id, chat_id], countdown=600)`. Bot restart'da ham ishlaydi (Celery broker = Redis db1). Alternative: APScheduler `add_job(run_date=now+10min)` |

**Mavjud mexanizm bilan bog'lanish**:
- Hozirda `apps/bot/handlers/private/ai_followups.py` da `_catalog_followup_task()` mavjud — `asyncio.sleep(random.randint(300, 600))` bilan ishlaydi
- Mavjud dedup: `CacheKeys.catalog_followup_sent(user_id)` — `madina:catalog_followup:{user_id}` 24h TTL
- **Integratsiya**: yangi tizim mavjud `_catalog_followup_task` ni almashtiradi, ammo shu Redis key'ni ishlatishda davom etadi

```python
# infrastructure/queue/tasks/agent_followup_tasks.py
from celery import shared_task

@shared_task(name="agent.catalog_followup", bind=True, max_retries=1)
def send_catalog_followup(self, user_id: int, chat_id: int) -> None:
    """Catalog follow-up: 10 min after OPENED_CATALOG, if no further action."""
    import asyncio
    asyncio.run(_send_catalog_followup_async(user_id, chat_id))

async def _send_catalog_followup_async(user_id: int, chat_id: int) -> None:
    # 1. Check dedup: agent:fu:catalog:{user_id} exists? -> return
    # 2. Check stop conditions
    # 3. Check FSM state (not in order/pricing/lead_capture)
    # 4. Check business hours
    # 5. Load memory for personalization
    # 6. Compose message via MessageComposerService
    # 7. Send via Bot
    # 8. Set dedup key: agent:fu:catalog:{user_id} NX 24h
    # 9. Record in agent memory: follow_up_history.append(...)
```

---

### B) PRICE FOLLOW-UP (10 daqiqa)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | `PRICE_CALCULATED` — foydalanuvchi narx hisoblab oldi, lekin 10 daqiqa ichida buyurtma bermadi va boshqa harakat qilmadi |
| **Delay** | 10 daqiqa (600 soniya) |
| **Condition (qachon yuborish)** | 1) Foydalanuvchi narx oldi lekin buyurtma bermadi. 2) FSM state'da emas. 3) Business hours. 4) Oxirgi 2 soatda price_followup yuborilmagan |
| **Condition (qachon yuborMASLIK)** | 1) Foydalanuvchi buyurtma boshladi (state = ORDERING). 2) Telefon yubordi. 3) Operator so'radi. 4) Oxirgi 2 soatda price_followup allaqachon yuborilgan |
| **Message** | "💰 {design_name} uchun {area}m² narxi — {price} so'm. Hozir buyurtma bersangiz bepul o'lchov + 15 yil kafolat! Buyurtma berasizmi? 👇" |
| **Inline buttons** | `[🛒 Buyurtma berish]` (callback: `agent:order:{user_id}`) + `[📞 Operator bilan bog'lanish]` (callback: `agent:operator:{user_id}`) |
| **Max yuborish** | 1 marta per event, 2 marta per 24 soat |
| **Cooldown** | 2 soat (CacheTTL: 7_200) |
| **Stop conditions** | 1) Foydalanuvchi buyurtma berdi. 2) Operator bilan bog'landi. 3) "kerak emas" dedi. 4) DEAL/LOST state |
| **Admin escalation** | HA — 2-chi price follow-up'dan keyin javob bo'lmasa: "Mijoz narx oldi lekin buyurtma bermadi (2x eslatma)" admin alert |
| **Redis key (dedup)** | `agent:fu:price:{user_id}` — TTL 7_200 (2h), NX flag |
| **Redis key (daily count)** | `agent:fu:price:daily:{user_id}` — TTL 90_000 (25h), INCR. Max = 2 |
| **Scheduler integration** | **Celery delayed task**: `send_price_followup.apply_async(args=[user_id, chat_id, event_data], countdown=600)` |

**Message personalization**:
```python
# MessageComposerService da:
def compose_price_followup(self, memory: dict) -> ComposedMessage:
    quote = memory.get("last_price_quote", {})
    design = quote.get("design", "potolok")
    area = quote.get("area_m2", "")
    price = f"{quote.get('total_price', 0):,}"

    text = (
        f"💰 {design} uchun {area}m² narxi — {price} so'm. "
        f"Hozir buyurtma bersangiz bepul o'lchov + 15 yil kafolat! "
        f"Buyurtma berasizmi? 👇"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Buyurtma berish", callback_data=f"agent:order:{user_id}"),
            InlineKeyboardButton(text="📞 Operator", callback_data=f"agent:operator:{user_id}"),
        ]
    ])
    return ComposedMessage(text=text, keyboard=kb)
```

---

### C) ABANDONED ORDER FOLLOW-UP (10 daqiqa)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | `ORDER_FORM_ABANDONED` — foydalanuvchi buyurtma formasini boshladi (OrderStates.*) lekin 10 daqiqa ichida davom etmadi |
| **Delay** | 10 daqiqa (600 soniya) nofaollikdan keyin. Timer har bir form qadam o'tishda reset bo'ladi |
| **Condition (qachon yuborish)** | 1) Foydalanuvchi hali OrderStates.* da (form tashlab ketmagan, boshqa joyga o'tmagan). 2) Oxirgi 10 daqiqada hech narsa yozmagan. 3) Business hours |
| **Condition (qachon yuborMASLIK)** | 1) Foydalanuvchi formani to'ldirdi (buyurtma tugadi). 2) Foydalanuvchi /cancel bilan chiqdi. 3) Boshqa FSM state'ga o'tdi |
| **Message** | "📝 Buyurtmangiz yarim qoldi! Davom etasizmi? Qolgan {remaining_steps} qadam qoldi. Tayyor paketlarimizni ko'rishni xohlaysizmi?" |
| **Inline buttons** | `[✅ Davom etish]` (callback: `agent:resume_order:{user_id}`) + `[🎁 Paketlar]` (callback: `agent:packages:{user_id}`) + `[❌ Bekor qilish]` (callback: `agent:cancel_order:{user_id}`) |
| **Max yuborish** | 1 marta per abandoned form |
| **Cooldown** | 6 soat (CacheTTL: 21_600) |
| **Stop conditions** | 1) Foydalanuvchi formani davom etdi. 2) Buyurtma berdi. 3) Bekor qildi |
| **Admin escalation** | HA — "Mijoz buyurtma formani tashlab ketdi" alert. Admin card: ism, telefon (agar bor), qaysi bosqichda tashlab ketdi, score |
| **Redis key (dedup)** | `agent:fu:order_abandon_sent:{user_id}` — TTL 21_600 (6h), NX |
| **Redis key (timer)** | `agent:fu:order_track:{user_id}` — TTL 660 (11 min). Har bir form step'da EXPIRE reset. TTL expired = abandoned |
| **Scheduler integration** | **Celery delayed task** YOKI **APScheduler one-shot**: order form entry da 10 min delay bilan schedule. Har bir step'da: agar scheduled task bor — cancel + reschedule (yoki Redis TTL reset) |

**Remaining steps hisobi**:
```python
ORDER_STEPS = [
    "waiting_for_name",
    "waiting_for_phone",
    "waiting_for_district",
    "waiting_for_category",
    "waiting_for_area",
    "waiting_for_location",
]

def _count_remaining(last_step: str) -> int:
    try:
        idx = ORDER_STEPS.index(last_step)
        return len(ORDER_STEPS) - idx - 1
    except ValueError:
        return 3  # fallback
```

---

### D) PHONE REMINDER (15 daqiqa)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | `PRICE_CALCULATED` — narx hisoblab olgandan keyin, agar telefon hali yuborilmagan bo'lsa |
| **Delay** | 15 daqiqa (900 soniya) — narx follow-up'dan 5 daqiqa keyin |
| **Condition (qachon yuborish)** | 1) `memory.phone_captured == false`. 2) Narx hisoblab olgan (last_price_quote bor). 3) Business hours. 4) Oxirgi 24 soatda phone_reminder yuborilmagan |
| **Condition (qachon yuborMASLIK)** | 1) Telefon allaqachon yuborilgan (`phone_captured = true`). 2) Buyurtma bergan. 3) Operator so'ragan |
| **Message** | "Salom {name}! Narx hisoblagansiz — aniqroq ma'lumot uchun telefon raqamingizni yuboring 📱\nUstamiz bepul o'lchov qilib beradi!" |
| **Inline buttons** | Yo'q — matn xabari. Foydalanuvchi o'zi telefon yozadi yoki contact share qiladi |
| **Max yuborish** | 1 marta per narx hisoblash sessiyasi |
| **Cooldown** | 24 soat (CacheTTL: 86_400) |
| **Stop conditions** | 1) Telefon yuborildi. 2) Buyurtma berdi. 3) Operator so'radi |
| **Admin escalation** | YO'Q — foydalanuvchiga yuboriladi, admin kerak emas |
| **Redis key (dedup)** | `agent:fu:phone_reminder:{user_id}` — TTL 86_400 (24h), NX |
| **Scheduler integration** | **Celery delayed task**: `send_phone_reminder.apply_async(args=[user_id, chat_id], countdown=900)` |

---

### E) 24H SOFT REMINDER (24 soat)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | Foydalanuvchi oxirgi marta bot bilan muloqot qilganidan beri 24 soat o'tdi. `ai:last_interaction:{user_id}` timestamp asosida aniqlanadi |
| **Delay** | 24 soat (86_400 soniya). Scheduler job orqali detect qilinadi (mavjud `check_inactive_leads` 15 min interval bilan ishlaydi) |
| **Condition (qachon yuborish)** | 1) Oxirgi faollik 24+ soat oldin. 2) Foydalanuvchi hali lead sifatida faol (LOST emas). 3) Hali 24h reminder yuborilmagan. 4) Business hours. 5) Lead score >= 15 (juda past score'li leadlarga yubormaslik) |
| **Condition (qachon yuborMASLIK)** | 1) Foydalanuvchi oxirgi 24 soatda faol bo'lgan. 2) Lead allaqachon LOST/DEAL. 3) `stop_follow_ups = true`. 4) Oxirgi 48 soatda 24h_reminder allaqachon yuborilgan |
| **Message** | "Salom {name}! 🙂 Natijnoy potolok bo'yicha savollaringiz qoldimi? Men yordam berishga tayyorman." |
| **Inline buttons** | Yo'q |
| **Max yuborish** | 1 marta per 48 soat |
| **Cooldown** | 48 soat (CacheTTL: 172_800) |
| **Stop conditions** | 1) Foydalanuvchi javob berdi. 2) Buyurtma berdi. 3) "kerak emas" dedi |
| **Admin escalation** | YO'Q |
| **Redis key (dedup)** | `agent:fu:soft_24h:{user_id}` — TTL 172_800 (48h), NX |
| **Scheduler integration** | **APScheduler interval job**: mavjud `check_inactive_leads` kengaytirish yoki alohida `check_soft_reminders` job (15 min interval) |

**Mavjud bilan integratsiya**:
- `apps/scheduler/jobs/followup_jobs.py` `check_inactive_leads()` — hozirda 24h/72h/7d tiered reminders yuboradi **admin**ga
- Yangi 24h soft reminder **foydalanuvchiga** yuboriladi (boshqa narsa)
- Ikki tizim parallel ishlaydi: admin 24h eslatma + user 24h soft reminder

---

### F) 72H FINAL OFFER (72 soat)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | 24h soft reminder yuborilgandan keyin hali 48 soat javob yo'q (jami 72 soat nofaollik) |
| **Delay** | 72 soat total (24h reminder + 48h qo'shimcha) |
| **Condition (qachon yuborish)** | 1) 24h reminder yuborilgan, javob yo'q. 2) Lead hali LOST emas. 3) Lead score >= 20. 4) Business hours |
| **Condition (qachon yuborMASLIK)** | 1) Foydalanuvchi javob berdi. 2) Allaqachon LOST/DEAL. 3) `stop_follow_ups = true` |
| **Message** | "Salom {name}! Sizga maxsus taklif: bugun buyurtma bersangiz 5% chegirma! 🎁\nQiziqsangiz yozing." |
| **Inline buttons** | `[🛒 Buyurtma]` (callback: `agent:order:{user_id}`) + `[📞 Qo'ng'iroq qiling]` (callback: `agent:call_request:{user_id}`) |
| **Max yuborish** | 1 marta per lead lifetime |
| **Cooldown** | Yo'q — faqat 1 marta yuboriladi |
| **Stop conditions** | 1) Foydalanuvchi javob berdi. 2) Buyurtma berdi |
| **Admin escalation** | HA — "72 soat javobsiz — oxirgi taklif yuborildi" admin alert. Agar bundan keyin ham javob bo'lmasa — 7 kunda `check_inactive_leads` LOST candidate qiladi |
| **Redis key (dedup)** | `agent:fu:final_72h:{user_id}` — TTL 2_592_000 (30 kun), NX. Faqat 1 marta yuboriladi |
| **Scheduler integration** | **APScheduler interval job**: mavjud `check_inactive_leads` kengaytirish — 72h inactive + 24h reminder sent + no reply = trigger |

---

### G) IMAGE RESPONSE (darhol)

| Parametr | Qiymat |
|----------|--------|
| **Trigger event** | `IMAGE_SENT` — foydalanuvchi shaxsiy chatda rasm yubordi |
| **Delay** | **0 daqiqa — DARHOL** |
| **Condition (qachon yuborish)** | 1) Rasm shaxsiy chatda yuborildi. 2) Har doim — bu yuqori niyat signali |
| **Condition (qachon yuborMASLIK)** | Yo'q — har doim admin alert yuboriladi |
| **Message (admin ga)** | "📸 <b>Mijoz xona rasmini yubordi!</b>\n\n👤 {name} | {phone}\n📍 {district}\n📊 Score: {score}\n\n<b>Tezda bog'laning!</b>" |
| **Inline buttons (admin ga)** | `[📌 Kanbanda ochish]` + `[📞 Qo'ng'iroq qilish]` |
| **Max yuborish** | Har bir rasm uchun 1 marta (har bir rasm muhim) |
| **Cooldown** | Yo'q |
| **Stop conditions** | Yo'q — har doim yuboriladi |
| **Admin escalation** | HA — **darhol** admin guruhga URGENT alert |
| **Redis key** | Kerak emas — har bir rasm unikal event |
| **Scheduler integration** | **Yo'q** — darhol yuboriladi, scheduler kerak emas. Mavjud `_enter_photo_funnel` orqali photo funnel boshlaydi |

**Mavjud bilan integratsiya**:
- `apps/bot/handlers/private/ai_support.py` `handle_photo_received()` — hozirda photo funnel boshlaydi (waiting_photo -> waiting_room -> waiting_area_photo)
- `apps/bot/handlers/private/ai_followups.py` `_photo_followup_task()` — 7 daqiqalik follow-up (photo funnel ichida)
- Yangi: admin alert qo'shiladi (hozirda yo'q — faqat foydalanuvchiga javob bor)

---

## 2. Follow-up Xabar Shablonlari (Hammasi)

```python
AGENT_FOLLOW_UP_MESSAGES: dict[str, dict] = {
    "catalog_followup": {
        "text": (
            "Salom {name} 😊 Katalogdagi qaysi model sizga yoqdi? "
            "Xonangiz kvadratini yozsangiz, taxminiy narxni "
            "1 daqiqada hisoblab beraman."
        ),
        "keyboard": None,
        "parse_mode": None,
    },
    "price_followup": {
        "text": (
            "💰 {design_name} uchun {area}m² narxi — {price} so'm. "
            "Hozir buyurtma bersangiz bepul o'lchov + 15 yil kafolat! "
            "Buyurtma berasizmi? 👇"
        ),
        "keyboard": [
            ["🛒 Buyurtma berish", "agent:order:{user_id}"],
            ["📞 Operator", "agent:operator:{user_id}"],
        ],
        "parse_mode": None,
    },
    "abandoned_order_followup": {
        "text": (
            "📝 Buyurtmangiz yarim qoldi! Davom etasizmi? "
            "Qolgan {remaining_steps} qadam qoldi. "
            "Tayyor paketlarimizni ko'rishni xohlaysizmi?"
        ),
        "keyboard": [
            ["✅ Davom etish", "agent:resume_order:{user_id}"],
            ["🎁 Paketlar", "agent:packages:{user_id}"],
            ["❌ Bekor qilish", "agent:cancel_order:{user_id}"],
        ],
        "parse_mode": None,
    },
    "phone_reminder": {
        "text": (
            "Salom {name}! Narx hisoblagansiz — aniqroq ma'lumot "
            "uchun telefon raqamingizni yuboring 📱\n"
            "Ustamiz bepul o'lchov qilib beradi!"
        ),
        "keyboard": None,
        "parse_mode": None,
    },
    "soft_24h_reminder": {
        "text": (
            "Salom {name}! 🙂 Natijnoy potolok bo'yicha "
            "savollaringiz qoldimi? Men yordam berishga tayyorman."
        ),
        "keyboard": None,
        "parse_mode": None,
    },
    "final_72h_offer": {
        "text": (
            "Salom {name}! Sizga maxsus taklif: "
            "bugun buyurtma bersangiz 5% chegirma! 🎁\n"
            "Qiziqsangiz yozing."
        ),
        "keyboard": [
            ["🛒 Buyurtma berish", "agent:order:{user_id}"],
            ["📞 Qo'ng'iroq qiling", "agent:call_request:{user_id}"],
        ],
        "parse_mode": None,
    },
    "image_admin_alert": {
        "text": (
            "📸 <b>Mijoz xona rasmini yubordi!</b>\n\n"
            "👤 {name} | {phone}\n"
            "📍 {district}\n"
            "📊 Score: {score}\n\n"
            "<b>Tezda bog'laning!</b>"
        ),
        "keyboard": [
            ["📌 Kanbanda ochish", "kanban:lead:{lead_id}:new"],
            ["📞 Qo'ng'iroq", "agent:call:{user_id}"],
        ],
        "parse_mode": "HTML",
    },
}
```

---

## 3. Anti-Spam Kafolatlari

### Kunlik Limit

```python
# Har bir foydalanuvchiga kuniga max follow-up soni
MAX_FOLLOWUPS_PER_DAY = 3

# Redis key: agent:fu:daily:{user_id}
# Mexanizm: INCR + EXPIRE 25h
# Har bir follow-up yuborishdan oldin:
daily_count = await redis.incr(CacheKeys.agent_fu_daily(user_id))
if daily_count == 1:
    await redis.expire(key, CacheTTL.AGENT_FU_DAILY)  # 25h
if daily_count > MAX_FOLLOWUPS_PER_DAY:
    return  # bugun yetarli
```

### Soatlik Limit

```python
# Har qanday 2 ta follow-up orasida minimum gap
MIN_GAP_SECONDS = 3600  # 1 soat

# Redis key: agent:fu:last:{user_id}
# Mexanizm: SET NX + TTL
was_set = await redis.set(
    CacheKeys.agent_fu_last(user_id),
    str(int(time.time())),
    ttl=MIN_GAP_SECONDS,
    nx=True,
)
if not was_set:
    return  # hali erta — oldingi follow-up'dan 1 soat o'tmagan
```

### Per-Type Limit

```python
PER_TYPE_LIMITS = {
    "catalog_followup":          {"max_per_24h": 1, "cooldown_seconds": 86_400},
    "price_followup":            {"max_per_24h": 2, "cooldown_seconds": 7_200},
    "abandoned_order_followup":  {"max_per_24h": 1, "cooldown_seconds": 21_600},
    "phone_reminder":            {"max_per_24h": 1, "cooldown_seconds": 86_400},
    "soft_24h_reminder":         {"max_per_24h": 1, "cooldown_seconds": 172_800},
    "final_72h_offer":           {"max_per_24h": 1, "cooldown_seconds": 2_592_000},
    "image_admin_alert":         {"max_per_24h": 99, "cooldown_seconds": 0},  # limit yo'q
}
```

### Umumiy Zanjir Uzunligi

```python
# Bitta foydalanuvchiga umumiy follow-up chain uzunligi
MAX_CHAIN_LENGTH = 5  # Mavjud _MAX_FOLLOWUP_COUNT bilan bir xil

# Agent memory'da follow_up_history[] soni tekshiriladi
history = memory.get("follow_up_history", [])
if len(history) >= MAX_CHAIN_LENGTH:
    return  # yetarli — boshqa yubormaslik
```

---

## 4. Mavjud FollowupService Bilan Integratsiya

### Hozirgi Arxitektura

```
FollowupService (admin-facing)         Agent Follow-up Engine (user-facing)
├── process_due_followups() [60s]      ├── catalog_followup [10 min delay]
├── FollowupBrainService               ├── price_followup [10 min delay]
├── brain-driven type selection         ├── abandoned_order [10 min delay]
├── Max 5 per lead                      ├── phone_reminder [15 min delay]
├── Business hours aware                ├── soft_24h [24h delay]
├── Admin cards only                    ├── final_72h [72h delay]
└── DB-based (next_follow_up_at)        └── image_alert [immediate]
         |                                       |
         v                                       v
    Admin DM / Group                        User DM + Admin Group
```

### Parallel Ishlash

1. **FollowupService** admin'ga eslatma yuboradi (mavjud — o'zgarmaydi)
2. **Agent Follow-up Engine** foydalanuvchiga follow-up yuboradi (yangi)
3. Ikki tizim bir-birini biladi — `agent memory` orqali sync:
   - Agent follow-up yuborilganda `follow_up_history` ga yoziladi
   - FollowupBrainService `follow_up_count` ni ko'radi
   - Agar user reply bersa — ikkala tizim ham to'xtaydi

### _MAX_FOLLOWUP_COUNT = 5 Integratsiya

```python
# Mavjud hard cap saqlanadi:
# followup_service.py: _MAX_FOLLOWUP_COUNT = 5
# followup_brain_service.py: MAX_FOLLOWUP_COUNT = 5

# Agent follow-up engine ham shu limitni hurmat qiladi:
async def _check_total_followup_count(user_id: int) -> bool:
    """Combined count of admin + agent follow-ups."""
    # DB: lead.follow_up_count (admin follow-ups)
    # Memory: len(follow_up_history) (agent follow-ups)
    # Total must be < 5
    total = db_count + agent_count
    return total < 5
```

---

## 5. Mavjud CacheKeys Kengaytirish

### Hozirgi AI Follow-up Keys

```python
# Mavjud (o'zgarmaydi):
CacheKeys.ai_followup_nonce(user_id)      # madina:followup_nonce:{user_id}  TTL 2h
CacheKeys.ai_followup_state(user_id)      # ai:followup_state:{user_id}     TTL 24h
CacheKeys.ai_last_interaction(user_id)    # ai:last_interaction:{user_id}   TTL 24h
CacheKeys.catalog_followup_sent(user_id)  # madina:catalog_followup:{user_id} TTL 24h
```

### Yangi Agent Follow-up Keys

```python
# infrastructure/cache/keys.py ga qo'shiladi:

class CacheTTL:
    # ... mavjud TTL'lar ...

    # Agent follow-up engine
    JOURNEY_STATE               = 2_592_000   # 30 kun
    AGENT_FU_DAILY_COUNT        = 90_000      # 25h — kunlik counter
    AGENT_FU_LAST_SENT          = 3_600       # 1h — min gap
    AGENT_FU_CATALOG            = 86_400      # 24h — catalog cooldown
    AGENT_FU_PRICE              = 7_200       # 2h — price cooldown
    AGENT_FU_ORDER_ABANDON      = 21_600      # 6h — order abandon cooldown
    AGENT_FU_ORDER_TRACK        = 660         # 11 min — order form timer
    AGENT_FU_PHONE_REMINDER     = 86_400      # 24h — phone reminder cooldown
    AGENT_FU_SOFT_24H           = 172_800     # 48h — 24h reminder cooldown
    AGENT_FU_FINAL_72H          = 2_592_000   # 30 kun — one-time final offer


class CacheKeys:
    # ... mavjud key'lar ...

    # ── Agent journey ──────────────────────────────────────────────────
    @staticmethod
    def journey_state(user_id: int) -> str:
        return f"journey:state:{user_id}"

    # ── Agent follow-up dedup ──────────────────────────────────────────
    @staticmethod
    def agent_fu_daily(user_id: int) -> str:
        """Daily follow-up counter."""
        return f"agent:fu:daily:{user_id}"

    @staticmethod
    def agent_fu_last(user_id: int) -> str:
        """Last follow-up timestamp (min gap enforcement)."""
        return f"agent:fu:last:{user_id}"

    @staticmethod
    def agent_fu_cooldown(user_id: int, fu_type: str) -> str:
        """Per-type follow-up cooldown."""
        return f"agent:fu:{fu_type}:{user_id}"

    @staticmethod
    def agent_fu_order_track(user_id: int) -> str:
        """Order form activity tracker (10 min TTL)."""
        return f"agent:fu:order_track:{user_id}"
```

---

## 6. Scheduler Persistence: Bot Restart'da Nima Bo'ladi?

### Muammo

Hozirgi `asyncio.sleep` based follow-up'lar (ai_followups.py) bot restart'da yo'qoladi. Masalan:
- Bot catalog follow-up uchun `asyncio.sleep(600)` qildi
- Bot 5 daqiqadan keyin restart bo'ldi
- Follow-up yo'qoldi — foydalanuvchi xabar olmaydi

### Yechim: Celery + APScheduler Hybrid

```
                    ┌────────────────────────────┐
                    │    PERSISTENCE STRATEGY      │
                    │                              │
                    │  Qisqa delay (< 15 min):     │
                    │  ├── Celery delayed task      │
                    │  ├── Redis broker (db1)       │
                    │  └── eta= now + delay         │
                    │      Bot restart = safe        │
                    │      (Celery worker qayta      │
                    │       olib ishlaydi)           │
                    │                              │
                    │  Uzun delay (> 15 min):       │
                    │  ├── APScheduler one-shot     │
                    │  ├── run_date= now + delay    │
                    │  └── PostgreSQL job store      │
                    │      Bot restart = safe        │
                    │      (APScheduler qayta        │
                    │       yuklaydi)               │
                    │                              │
                    │  Fallback:                    │
                    │  ├── scheduled_followups       │
                    │  │   table (PostgreSQL)        │
                    │  ├── Checker job (30s)         │
                    │  └── fire_at <= now AND        │
                    │      status = 'pending'        │
                    │      = send immediately        │
                    │                              │
                    └────────────────────────────┘
```

### Celery Task (Qisqa Delay)

```python
# infrastructure/queue/tasks/agent_followup_tasks.py

from celery import shared_task

@shared_task(
    name="agent.send_followup",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def send_agent_followup(
    self,
    user_id: int,
    chat_id: int,
    follow_up_type: str,
    event_data: dict,
) -> None:
    """Send a scheduled follow-up message to a user."""
    import asyncio
    asyncio.run(_send_followup_async(user_id, chat_id, follow_up_type, event_data))
```

### APScheduler Job Store (Uzun Delay)

```python
# apps/scheduler/main.py da:
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    timezone="Asia/Tashkent",
    jobstores={
        "default": SQLAlchemyJobStore(url=settings.db.sync_url),  # persistent
    },
    job_defaults={...},
)
```

### Fallback: Database Checker

```python
# apps/scheduler/jobs/agent_followup_jobs.py

async def process_agent_followups() -> None:
    """Fallback: every 30s check scheduled_followups table."""
    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    async with factory() as session:
        # SELECT * FROM scheduled_followups
        # WHERE fire_at <= now AND status = 'pending'
        # ORDER BY fire_at ASC
        # LIMIT 20
        pending = await repo.get_pending(now, limit=20)
        for fu in pending:
            # 1. Re-check stop conditions
            # 2. Compose message
            # 3. Send
            # 4. UPDATE status = 'sent', sent_at = now
```

---

## 7. Duplicate Prevention: Redis NX Pattern

### Tamoyil

Har bir follow-up yuborishdan oldin Redis NX (SET if Not eXists) orqali dedup qilinadi. Bu **idempotent** yuborishni kafolatlaydi — hatto Celery task ikki marta ishga tushsa ham, foydalanuvchi faqat 1 marta xabar oladi.

### Pattern

```python
async def _try_send_with_dedup(
    redis: CacheClient,
    user_id: int,
    fu_type: str,
    ttl: int,
    send_fn: Callable,
) -> bool:
    """
    1. SET NX dedup key
    2. If acquired -> send
    3. If not acquired -> skip (already sent)
    """
    dedup_key = CacheKeys.agent_fu_cooldown(user_id, fu_type)
    acquired = await redis.set(dedup_key, "1", ttl=ttl, nx=True)

    if not acquired:
        log.info("followup_dedup_skip", user_id=user_id, type=fu_type)
        return False

    try:
        await send_fn()
        return True
    except TelegramForbiddenError:
        # User blocked bot
        log.info("followup_user_blocked", user_id=user_id)
        await _mark_stop(user_id, "user_blocked_bot")
        return False
    except TelegramRetryAfter as e:
        # Rate limited — retry after
        await asyncio.sleep(e.retry_after)
        await send_fn()
        return True
    except Exception:
        # Boshqa xatolik — dedup key'ni o'chirib, keyingi urinish uchun imkon berish
        await redis.delete(dedup_key)
        log.exception("followup_send_error", user_id=user_id, type=fu_type)
        return False
```

### Dedup Key Lifecycle

```
Follow-up scheduled ──► Celery/APScheduler delay ──► Task fires
    │                                                    │
    │                                              Check dedup key
    │                                                    │
    │                                              ┌─────┴─────┐
    │                                              │ NX = true │ Key yo'q
    │                                              │ (acquired) │ = yuborish
    │                                              └─────┬─────┘
    │                                                    │
    │                                              Set dedup key
    │                                              (TTL = cooldown)
    │                                                    │
    │                                              Send message
    │                                                    │
    │                                              Record in memory
    │                                                    │
    v                                                    v
Follow-up sent ────────────────────────── Dedup key expires after TTL
                                          (next follow-up allowed)
```

---

## 8. To'liq Follow-up Flow Diagrammasi

```
User Action (catalog/price/order)
        │
        v
  JourneyEventService.emit()
        │
        ├──► JourneyStateService.transition()
        │         │
        │         v
        │    Update Redis state
        │
        ├──► AgentMemoryService.update_from_event()
        │         │
        │         v
        │    Update memory fields
        │
        └──► AgentFollowupScheduler.schedule()
                  │
                  v
            ┌─────────────────────┐
            │ Safety Checks       │
            │ 1. Stop conditions  │
            │ 2. Daily limit      │
            │ 3. Per-type cooldown│
            │ 4. Min gap          │
            │ 5. Business hours   │
            └────────┬────────────┘
                     │
              All pass?
              ┌──────┴──────┐
              │ YES         │ NO
              v             v
        Schedule task    Log skip
        (Celery/APSch)   reason
              │
              │ ... delay (10 min / 15 min / 24h / 72h) ...
              │
              v
        Task fires
              │
              v
        ┌──────────────────────┐
        │ Re-check Conditions  │
        │ 1. User replied?     │
        │ 2. User ordered?     │
        │ 3. User said "no"?   │
        │ 4. Pipeline changed? │
        │ 5. Dedup NX check    │
        └────────┬─────────────┘
                 │
          All pass?
          ┌──────┴──────┐
          │ YES         │ NO
          v             v
    Compose message   Cancel
    (personalized)    (log reason)
          │
          v
    Send via Bot.send_message()
          │
          ├──► Record in memory
          ├──► Increment daily counter
          ├──► Set dedup key (NX + TTL)
          └──► Check admin escalation
                    │
              Need escalation?
              ┌──────┴──────┐
              │ YES         │ NO
              v             v
        Send admin alert   Done
        (enriched card)
```

---

## 9. Callback Handler'lar (Yangi)

Follow-up xabarlarida inline button'lar bor. Bu button'lar uchun callback handler'lar kerak:

```python
# apps/bot/handlers/callbacks/agent_followup_callbacks.py

router = Router(name="callbacks:agent_followup")

@router.callback_query(F.data.startswith("agent:order:"))
async def cb_agent_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Follow-up 'Buyurtma berish' button -> order flow boshlash."""
    await callback.answer()
    # 1. Journey event: CLICKED_ORDER emit
    # 2. Cancel all pending follow-ups
    # 3. Order flow boshlash
    from apps.bot.handlers.private.order import start_order_flow
    await start_order_flow(callback.message, state)

@router.callback_query(F.data.startswith("agent:operator:"))
async def cb_agent_operator(callback: CallbackQuery, state: FSMContext) -> None:
    """Follow-up 'Operator' button -> operator flow boshlash."""
    await callback.answer()
    # 1. Journey event: OPERATOR_REQUESTED emit
    # 2. Cancel all pending follow-ups
    from apps.bot.handlers.private.operator import start_operator_flow
    await start_operator_flow(callback.message, state)

@router.callback_query(F.data.startswith("agent:resume_order:"))
async def cb_resume_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Abandoned order 'Davom etish' button -> FSM state restore."""
    await callback.answer()
    # FSM state'ni restore qilish (last_step ga qaytarish)
    # Order formani shu joydan davom ettirish

@router.callback_query(F.data.startswith("agent:packages:"))
async def cb_agent_packages(callback: CallbackQuery, state: FSMContext) -> None:
    """Abandoned order 'Paketlar' button -> packages flow."""
    await callback.answer()
    from apps.bot.handlers.private.packages import show_packages
    await show_packages(callback.message, state)

@router.callback_query(F.data.startswith("agent:cancel_order:"))
async def cb_cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Abandoned order 'Bekor qilish' button."""
    await callback.answer()
    await state.clear()
    # Mark stop_follow_ups = true for order type
    await callback.message.answer(
        "Buyurtma bekor qilindi. Keyinroq qayta urinib ko'rishingiz mumkin 🙂",
        reply_markup=main_menu_keyboard(),
    )

@router.callback_query(F.data.startswith("agent:call_request:"))
async def cb_call_request(callback: CallbackQuery, state: FSMContext) -> None:
    """72h final offer 'Qo'ng'iroq qiling' button -> admin alert."""
    await callback.answer("Mutaxassisimiz tez orada qo'ng'iroq qiladi! ✅")
    # Admin guruhga: "Mijoz qo'ng'iroq so'radi" alert
```

**Router registration** (`apps/bot/main.py`):
```python
# callbacks_router.include_routers() ga qo'shiladi:
from apps.bot.handlers.callbacks.agent_followup_callbacks import router as agent_followup_callbacks_router

callbacks_router.include_routers(
    agent_followup_callbacks_router,  # agent:* — follow-up CTA buttons
    # ... mavjud callbacks ...
)
```

---

## 10. Monitoring va Analytics

### Follow-up Samaradorligi

```python
# Har bir follow-up yuborilganda qayd qilinadi:
AGENT_FOLLOWUP_METRICS = {
    "total_sent": "agent:metrics:sent:{date}",           # jami yuborilgan
    "total_replied": "agent:metrics:replied:{date}",     # javob olgan
    "total_converted": "agent:metrics:converted:{date}", # buyurtma bergan
    "total_skipped": "agent:metrics:skipped:{date}",     # skip qilingan
    "total_stopped": "agent:metrics:stopped:{date}",     # stop qilingan

    # Per-type breakdown
    "sent_by_type": "agent:metrics:sent:{date}:{type}",
    "replied_by_type": "agent:metrics:replied:{date}:{type}",
}
```

### Admin /agent_stats Command

```
📊 Agent Follow-up Statistika (bugun)

Yuborilgan: 45
├ Catalog: 12 (4 javob = 33%)
├ Price: 18 (8 javob = 44%)
├ Abandoned: 5 (3 davom = 60%)
├ Phone: 3 (1 yubordi = 33%)
├ 24h Soft: 5 (1 javob = 20%)
└ 72h Final: 2 (0 javob = 0%)

Skip qilingan: 23
├ Cooldown: 8
├ Daily limit: 5
├ Stop condition: 7
└ Business hours: 3

Konversiya: 6 buyurtma (13.3%)
```
