# 07 — Telegram UX Flows

> Complete Telegram UX flows with button layouts, state diagrams, and
> interaction sequences for every user-facing feature.

---

## Button Design Principles

| Principle | Rule |
|-----------|------|
| **Max buttons per row** | 3 buttons (inline keyboard) |
| **Primary action** | Always first (leftmost) |
| **Escape option** | Always include "Orqaga" or "Bekor" |
| **Emoji consistency** | Same emoji per intent across all flows |
| **Text length** | Button text max 20 characters |

### Emoji intent mapping

| Emoji | Intent | Usage |
|-------|--------|-------|
| `🛒` | Order / purchase | Buyurtma berish |
| `💰` | Price / calculation | Narx hisoblash |
| `📚` | Catalog / browse | Katalog |
| `📞` | Operator / call | Operator bilan bog'lanish |
| `❌` | Cancel / stop | Bekor qilish, Kerak emas |
| `⬅️` | Back / return | Orqaga, Menyu |
| `📱` | Phone / contact | Telefon yuborish |
| `📍` | Location / district | Joylashuv |
| `📐` | Measurement | Bepul o'lchov |
| `📦` | Packages | Tayyor paketlar |
| `🎁` | Promotions | Aksiyalar |
| `📋` | My orders | Buyurtmalarim |
| `ℹ️` | About / info | Biz haqimizda |
| `🤖` | AI assistant | Madina AI |
| `🔄` | Recalculate | Qayta hisoblash |
| `✅` | Confirm / continue | Davom etish |
| `📩` | Direct message | Shaxsiy xabar |

---

## 1. START FLOW

### Entry points

- `/start` command (DM or group deep-link)
- First message to bot

### Flow diagram

```
User sends /start
      │
      ├── [Returning user with memory]
      │       │
      │       └── Personalized greeting:
      │           "Salom yana Bobur 🙂
      │            Zakazingiz bo'yicha yoki boshqa savol bormi?"
      │
      └── [New user]
              │
              └── "Salom! Men Madina, VASHPOTOLOK yordamchisiman 😊
                   Natijnoy patalok haqida yordam beraman."
                        │
                        └── Main Menu (ReplyKeyboard, 3x3 grid)
```

### Main Menu Keyboard Layout

```
┌──────────────┬──────────────┬──────────────┐
│  💰 Narx     │  📚 Katalog  │  📦 Paketlar │
├──────────────┼──────────────┼──────────────┤
│  🛒 Buyurtma │  📐 O'lchov  │  📞 Operator │
├──────────────┼──────────────┼──────────────┤
│  🎁 Aksiyalar│  📋 Zakazlar │  ℹ️ Biz haq. │
└──────────────┴──────────────┴──────────────┘
```

Type: `ReplyKeyboardMarkup` (persistent, resize_keyboard=True)

### Deep-link routing (`/start {payload}`)

| Payload | Handler | Action |
|---------|---------|--------|
| `zakaz` | `order.py` | Start order flow |
| `price` | `pricing.py` | Start price calculator |
| `katalog` | `catalog.py` | Show catalog |
| `paketlar` | `packages.py` | Show packages |
| `orders` | `my_orders.py` | Show user's orders |
| `operator` | `operator.py` | Request operator |
| `discounts` | `promotions.py` | Show promotions |
| `ai` | `ai_support.py` | Enter AI chat |
| `about` | `about.py` | Show about info |

---

## 2. CATALOG FLOW

### Flow diagram

```
User taps "📚 Katalog" or sends /catalog
      │
      └── "📂 Katalog — Bo'limni tanlang:"
          │
          └── Inline keyboard (design list, 2 per row):
              ┌────────────────┬────────────────┐
              │   ✨ Gulli     │  ⚪ Adnatonniy  │
              ├────────────────┼────────────────┤
              │   💎 Mramor    │  🔷 Hi Tech    │
              ├────────────────┼────────────────┤
              │   🌟 Naqsh     │  🌌 Kosmos     │
              ├────────────────┼────────────────┤
              │   ☁️ Osmon     │  🖤 Qora UF    │
              ├────────────────┼────────────────┤
              │   🍽️ Oshxona   │  📐 Naqsh Oq   │
              └────────────────┴────────────────┘
                        │
                        └── [Design tapped]
                                │
                                └── Photo gallery + description + price range
                                    │
                                    └── Inline buttons:
                                        ┌────────────────┬────────────────┐
                                        │ 💰 Narx hisob. │  ⬅️ Orqaga    │
                                        └────────────────┴────────────────┘
                                                │
                                                ├── [💰 tapped] → Calculator Flow (pre-filled design)
                                                └── [⬅️ tapped] → Back to design list
```

### AI-detected catalog intent

When user mentions a room or design in free text:

```
User: "mehmonxona uchun variant ko'rsating"
      │
      └── Smart catalog response:
          "Katalogimizda har xil xonalar uchun dizaynlar bor 😊

           Albatta! Bizda Mehmonxona uchun ham turli dizaynlar bor.
           👇 To'liq katalogimizni shu knopkadan oching."
          │
          └── Inline button:
              ┌──────────────────────────┐
              │ 📂 To'liq katalogimiz    │  (URL: t.me/vashpotolokuz)
              └──────────────────────────┘
```

### Catalog follow-up (5-10 min silence)

```
[5-10 min after catalog shown, no user action]
      │
      └── "Ko'rib chiqdizmi? 😊
           Xohlasangiz, bepul o'lchov uchun zakaz qabul qilib qo'yaymi?

           Qaysi tumandasiz va taxminiy maydon nechchi m²?"
      │
      └── ReplyKeyboard:
          ┌──────────────┐
          │  ⬅️ Menyu    │
          └──────────────┘
```

---

## 3. CALCULATOR FLOW

### Flow diagram

```
User taps "💰 Narx" or sends /price
      │
      └── "Xona o'lchamini yozing (masalan: 5x4 yoki 20)"
          │
          └── [User enters dimensions: "5x4" or "20" or "20 m2"]
                  │
                  └── Area parsed → Design selection:
                      "Qaysi tur kerak?"
                      │
                      └── Inline keyboard (2x3 + extras):
                          ┌────────────────┬────────────────┐
                          │  ⚪ Adnatonniy  │  🔷 Hi Tech    │
                          ├────────────────┼────────────────┤
                          │  💎 Mramor     │  🌟 Naqsh      │
                          ├────────────────┼────────────────┤
                          │  ☁️ Osmon      │  🖤 Qora UF    │
                          ├────────────────┼────────────────┤
                          │  ✨ Gulli      │                │
                          └────────────────┴────────────────┘
                                  │
                                  └── [Design tapped]
                                          │
                                          └── Quote card:
                                              "📐 Maydon: 20 m²
                                               🎨 Dizayn: Gulli
                                               💰 Narx: 2 800 000 so'm

                                               Xohlasangiz ustamiz kelib bepul
                                               o'lchov qilib beradi 🙂

                                               Qaysi tumandasiz?"
                                              │
                                              └── ReplyKeyboard:
                                                  ┌──────────────┐
                                                  │  ⬅️ Menyu    │
                                                  └──────────────┘
```

### AI-detected price calculation

When user includes area + design in a single message:

```
User: "Qarshida 25m² gulli potolok qancha?"
      │
      └── Combo detected: area=25, district=Qarshi, design=Gulli
          │
          └── Order summary card:
              "Zo'r 🙂

               📏 Maydon: 25 m²
               📍 Tuman: Qarshi
               🎨 Dizayn: Gulli

               Zakazni rasmiylashtirish uchun telefon
               raqamingizni yuboring 🙂"
              │
              └── Phone request keyboard:
                  ┌────────────────────────────────┐
                  │  📱 Telefonni yuborish          │  (request_contact=True)
                  ├────────────────────────────────┤
                  │  ❌ Bekor qilish                │
                  └────────────────────────────────┘
```

### Price table (area only, no district)

```
"20 m² uchun taxminiy narx:

 • Adnatonniy — 1 600 000 so'm
 • Hi Tech / Mramor / Naqsh / Kosmos / Osmon — 2 400 000 so'm
 • Qora UF — 2 800 000 so'm
 • Gulli — 2 400 000–2 800 000 so'm"
      │
      └── Inline button:
          ┌──────────────────────────┐
          │ 📂 To'liq katalogimiz    │
          └──────────────────────────┘
      │
      └── Upsell CTA:
          "Xohlasangiz ustamiz kelib bepul o'lchov qilib beradi 🙂
           Qaysi tumandasiz?"
```

---

## 4. ORDER FLOW

### Flow diagram (with back/cancel at every step)

```
User taps "🛒 Buyurtma" or sends /order
      │
      ├── Step 1: NAME
      │   "Ismingiz?"
      │   ReplyKeyboard: [⬅️ Orqaga | ❌ Bekor]
      │       │
      │       └── [User enters name: "Bobur"]
      │
      ├── Step 2: PHONE
      │   "Telefon raqamingiz?"
      │   ReplyKeyboard:
      │   ┌────────────────────────────────┐
      │   │  📱 Telefonni yuborish          │  (request_contact=True)
      │   ├────────────────────────────────┤
      │   │  ⬅️ Orqaga   │  ❌ Bekor       │
      │   └────────────────────────────────┘
      │       │
      │       ├── [Contact shared] → phone captured (score +40)
      │       └── [Text: "+998901234567"] → phone captured
      │
      ├── Step 3: DISTRICT
      │   "Tumaningiz?"
      │   Inline keyboard (13 districts, 3 per row):
      │   ┌──────────┬──────────┬──────────┐
      │   │  Qarshi   │ Shahri.  │  Kitob   │
      │   ├──────────┼──────────┼──────────┤
      │   │  Yakka.   │ Chiroq.  │  G'uzor  │
      │   ├──────────┼──────────┼──────────┤
      │   │  Koson    │  Kasbi   │  Mubo.   │
      │   ├──────────┼──────────┼──────────┤
      │   │  Nishon   │  Dehqon. │  Mirish. │
      │   ├──────────┼──────────┼──────────┤
      │   │  Qamashi  │          │  ⬅️      │
      │   └──────────┴──────────┴──────────┘
      │
      ├── Step 4: CEILING TYPE
      │   "Potolok turi?"
      │   Inline keyboard (10 types, 2 per row):
      │   ┌────────────────┬────────────────┐
      │   │   ✨ Gulli     │  ⚪ Adnatonniy  │
      │   ├────────────────┼────────────────┤
      │   │   💎 Mramor    │  🔷 Hi Tech    │
      │   ├────────────────┼────────────────┤
      │   │   ...          │  ⬅️ Orqaga     │
      │   └────────────────┴────────────────┘
      │
      ├── Step 5: ROOM SIZE
      │   "Xona o'lchami? (masalan: 5x4 yoki 20 m²)"
      │   ReplyKeyboard: [⏭ O'tkazish | ⬅️ Orqaga]
      │       │
      │       ├── [Dimensions entered] → area parsed
      │       └── [⏭ O'tkazish] → skip, no area
      │
      ├── Step 6: LOCATION (optional)
      │   "Joylashuvingiz?"
      │   ReplyKeyboard:
      │   ┌────────────────────────────────┐
      │   │  📍 Joylashuvni yuborish       │  (request_location=True)
      │   ├────────────────────────────────┤
      │   │  ⏭ O'tkazish  │  ⬅️ Orqaga   │
      │   └────────────────────────────────┘
      │
      └── CONFIRMATION
          "✅ Buyurtmangiz qabul qilindi!
           Operator tez orada bog'lanadi ☎️"
              │
              ├── Lead created in database
              ├── Pipeline stage: NEW
              ├── Admin notification sent (full intelligence card)
              └── Main menu keyboard restored
```

### Back navigation

Every "⬅️ Orqaga" button returns to the previous step's prompt. FSM tracks current step and restores state.

### Cancel behavior

"❌ Bekor" at any step:
1. Clears FSM state
2. Shows main menu
3. Preserves `order_form_progress` in memory (for abandoned form recovery)

---

## 5. FOLLOW-UP FLOW

### Agent-initiated follow-up sequence

```
[User completes an action, then goes silent]
      │
      ├── T+5-10 min (catalog follow-up)
      │   "Ko'rib chiqdizmi? 😊
      │    Xohlasangiz, bepul o'lchov uchun zakaz qabul qilib qo'yaymi?
      │    Qaysi tumandasiz va taxminiy maydon nechchi m²?"
      │
      ├── T+10 min (AI interaction follow-up)
      │   "Yordam kerakmi? 🙂
      │    Agar xohlasangiz:
      │    📏 Xona maydonini yozing
      │    yoki
      │    📍 Tumaningizni yozing
      │    Men sizga aniq narxni hisoblab beraman."
      │
      ├── T+60 min (AI interaction follow-up #2)
      │   "Agar xohlasangiz bepul o'lchov xizmatimiz ham bor 🙂
      │    Ustamiz kelib aniq narxni aytib beradi.
      │    Zakaz qoldirish uchun telefon raqamingizni yozishingiz mumkin."
      │
      ├── T+24 hr (admin reminder — scheduler)
      │   [Admin receives: "🟡 1-eslatma (24 soat) — Lid #123"]
      │
      ├── T+72 hr (admin reminder — scheduler)
      │   [Admin receives: "🔴 2-eslatma (72 soat) — Lid #123"]
      │
      └── T+7 days (auto-LOST — scheduler)
          [Admin receives: "⚠️ LOST candidate — Sabab: no_response"]
```

### User response handling

```
[Follow-up message sent]
      │
      ├── [User taps inline button]
      │       └── Route to appropriate flow (catalog, pricing, order)
      │           Follow-up timer cancelled (nonce refreshed)
      │
      ├── [User replies with text]
      │       └── AI handles the message
      │           Follow-up timer cancelled (nonce refreshed)
      │
      ├── [User says "kerak emas" / "bekor"]
      │       └── "Tushunaman! Fikringiz o'zgarsa, istalgan vaqt yozing.
      │            Yaxshi kun! 😊"
      │           All follow-ups cancelled
      │           Journey state → LOST (if explicitly rejected)
      │
      └── [No response]
              └── Next tier follow-up (see timeline above)
```

---

## 6. OPERATOR HANDOFF

### Flow diagram

```
User taps "📞 Operator" or says "operator bilan bog'lanish kerakman"
      │
      ├── [Phone already known]
      │       └── "Rahmat! Operator tez orada bog'lanadi ☎️"
      │           │
      │           └── Admin notification (with full lead context):
      │               "👔 Operator kerak!
      │                Mijoz: Bobur (@bobur_uz)
      │                📞 +998901234567
      │                📍 Qarshi
      │                🎯 Score: 65/100 (🔥HOT)
      │                So'nggi: price_calculated"
      │
      └── [Phone unknown]
              └── "Operator sizga qo'ng'iroq qiladi.
                   Telefon raqamingizni yuboring."
                  │
                  └── Phone request keyboard:
                      ┌────────────────────────────────┐
                      │  📱 Telefonni yuborish          │
                      ├────────────────────────────────┤
                      │  ❌ Bekor qilish                │
                      └────────────────────────────────┘
                          │
                          ├── [Contact shared]
                          │       └── "Rahmat! Operator tez orada bog'lanadi ☎️"
                          │           + Admin notification
                          │
                          └── [❌ Bekor]
                                  └── Return to main menu
```

---

## 7. GROUP to DM REDIRECT

### Flow diagram

```
[User in group chat taps URL menu button]
      │
      └── Deep-link URL → t.me/vashpotolok_bot?start={payload}
          │
          ├── [User already has DM with bot]
          │       └── Opens existing DM, processes deep-link payload
          │
          └── [First time user]
                  └── Opens DM → /start {payload} processed
                      Appropriate flow started based on payload
```

### Group inline menu (9 URL buttons)

Shown when bot joins a group as admin, and on first message per user per day.

```
Inline keyboard (3x3 URL buttons):
┌──────────────┬──────────────┬──────────────┐
│  🛒 Buyurtma │  💰 Narx     │  📚 Katalog  │
│  ?start=zakaz│  ?start=price│  ?start=kat. │
├──────────────┼──────────────┼──────────────┤
│  📦 Paketlar │  📋 Zakazlar │  📞 Operator │
│  ?start=pak. │  ?start=ord. │  ?start=oper.│
├──────────────┼──────────────┼──────────────┤
│  🎁 Aksiyalar│  🤖 AI       │  ℹ️ Biz haq. │
│  ?start=disc.│  ?start=ai   │  ?start=about│
└──────────────┴──────────────┴──────────────┘
```

All buttons are `InlineKeyboardButton(url=...)` pointing to `https://t.me/{bot_username}?start={payload}`.

### Group menu dedup

- `CacheKeys.grp_inline_menu_shown(chat_id, user_id)` with 24h TTL
- Each user sees the menu at most once per day per group
- Pinned menu (when bot is admin) has no per-user dedup

---

## 8. AI CHAT FLOW

### Entry and exit

```
[User sends free-text message in DM, not matching any command/button]
      │
      └── ai_support_router catches it (last in private_router priority)
          │
          ├── [First message — no name in memory]
          │       └── "Assalomu alaykum! Siz bilan tanishib olsam —
          │            ismingiz nima? 😊"
          │           FSM → AiSupportStates.waiting_for_name
          │
          ├── [Name collected]
          │       └── "Yordam beray, {ism}! Potolok haqida savolingiz bormi? 😊"
          │           FSM → AiSupportStates.waiting_for_ai_question
          │
          └── [Subsequent messages]
                  │
                  ├── [Greeting detected] → Short greeting + neutral CTA
                  ├── [Price query detected] → Price calculator flow
                  ├── [Catalog request detected] → Catalog link + smart response
                  ├── [Measurement request detected] → Measurement lead flow
                  ├── [Area detected in text] → Price table + upsell CTA
                  ├── [Objection detected] → Negotiation reply
                  ├── [Photo sent] → Photo funnel
                  └── [General question] → OpenAI API call → JSON response
```

### AI chat keyboard

During AI session, only one persistent button:

```
ReplyKeyboard:
┌──────────────┐
│  ⬅️ Menyu    │
└──────────────┘
```

Tapping "Menyu" exits AI mode and returns to main menu.

### Phone collection (within AI flow)

```
[AI detects user is ready to order / share phone]
      │
      └── "Zakazni rasmiylashtirish uchun telefon raqamingizni yuboring 🙂"
          FSM → AiSupportStates.waiting_for_phone
          │
          └── Phone request keyboard:
              ┌────────────────────────────────┐
              │  📱 Telefonni yuborish          │
              ├────────────────────────────────┤
              │  ❌ Bekor qilish                │
              └────────────────────────────────┘
```

### Photo funnel

```
[User sends a photo in AI mode]
      │
      └── "📸 Iltimos, xonangizni rasmini yuboring."
          FSM → AiSupportStates.waiting_photo
              │
              └── [Photo received]
                      │
                      └── Room type detection → Design recommendations
                          "Bu xona uchun tavsiya qilinadigan dizaynlar:
                           ✨ Gulli
                           ✨ Hi Tech
                           ..."
                          │
                          └── [7 min silence]
                                  └── "Ko'rib chiqdizmi? 🙂
                                       Xohlasangiz, bepul o'lchov uchun
                                       ustani yuborib qo'yaman.
                                       Qaysi tumandasiz?"
```

---

## 9. PACKAGES FLOW

### Flow diagram

```
User taps "📦 Tayyor paketlar" or sends /start paketlar
      │
      └── Package overview:
          "📦 Tayyor paketlar — o'zingizga qulay paketni tanlang:"
          │
          └── Inline keyboard:
              ┌──────────────────────────┐
              │  ⭐ Standard             │
              ├──────────────────────────┤
              │  💎 Premium              │
              ├──────────────────────────┤
              │  👑 VIP                  │
              └──────────────────────────┘
                      │
                      └── [Package tapped]
                              │
                              └── Package detail card:
                                  "💎 Premium paket
                                   ✅ Natijnoy potolok
                                   ✅ LED tasma
                                   ✅ Karniz
                                   ✅ Bepul o'lchov
                                   ✅ 15 yil kafolat
                                   📏 20 m² uchun: X so'm"
                                  │
                                  └── Inline buttons:
                                      ┌──────────────┬──────────────┐
                                      │ 🛒 Buyurtma  │ 💰 Hisoblash │
                                      ├──────────────┼──────────────┤
                                      │ ⬅️ Orqaga    │              │
                                      └──────────────┴──────────────┘
```

---

## 10. PROMOTIONS FLOW

```
User taps "🎁 Aksiyalar"
      │
      └── Current promotions card:
          "🎁 Joriy aksiyalar:

           1. Bepul o'lchov xizmati
           2. 20 m² dan — 5% chegirma
           3. 40 m² dan — 10% chegirma
           4. 15 yil kafolat"
          │
          └── Inline buttons:
              ┌──────────────────┬──────────────────┐
              │  💰 Narx hisob.  │  🛒 Buyurtma     │
              └──────────────────┴──────────────────┘
```

---

## 11. MY ORDERS FLOW

```
User taps "📋 Zakazlar" or sends /start orders
      │
      ├── [No orders found]
      │       └── "Sizda hali buyurtma yo'q.
      │            Buyurtma berasizmi?"
      │           Inline button: [🛒 Buyurtma berish]
      │
      └── [Orders found]
              └── Order list:
                  "📋 Buyurtmalaringiz:

                   #1 — Gulli, 20 m², Qarshi
                   📍 Status: O'rnatish kutilmoqda
                   📅 Sana: 2026-05-20

                   #2 — Hi Tech, 15 m², Shahrisabz
                   📍 Status: Bajarildi ✅
                   📅 Sana: 2026-05-15"
```

---

## 12. SALES CLOSER CTA

Triggered automatically when lead score and signals meet threshold.

### Trigger conditions

- Score >= 40
- Intent in {price, measurement, catalog}
- Any of: area_m2, phone_captured, confidence >= 0.6
- Cooldown: 10 minutes between attempts (Redis NX)

### CTA message

```
[Score threshold reached]
      │
      └── Closing CTA (inline buttons):
          ┌──────────────────────────┐
          │  📐 Bepul o'lchov        │
          ├──────────────────────────┤
          │  📞 Qo'ng'iroq so'rash   │
          ├──────────────────────────┤
          │  📚 Katalog ko'rish      │
          ├──────────────────────────┤
          │  💰 Narx hisoblash       │
          ├──────────────────────────┤
          │  ⏭ Keyinroq              │
          └──────────────────────────┘
```

### Callback handling

| Button | Callback Data | Action |
|--------|--------------|--------|
| Bepul o'lchov | `closer:book` | Start measurement lead flow |
| Qo'ng'iroq | `closer:call` | Request operator |
| Katalog | `closer:catalog` | Show catalog link |
| Narx hisoblash | `closer:price` | Start price calculator |
| Keyinroq | `closer:later` | Acknowledge, no action |

---

## 13. FAILSAFE UI

When an unrecoverable error occurs (OpenAI down, DB error):

```
"⚠️ Kechirasiz, texnik nosozlik yuz berdi.

 Operatorga murojaat qilishingiz mumkin:"
      │
      └── Inline button:
          ┌────────────────────────────────────┐
          │  📞 Operator bilan bog'lanish       │  (URL: t.me/ceiling_manager)
          └────────────────────────────────────┘
```

---

## 14. ADMIN NOTIFICATION CARDS

### New lead card (sent to admin group)

```
🆕 Yangi lid

📋 Lead #42
👤 Bobur (@bobur_uz)
📞 +998901234567
📍 Qarshi
📏 25 m² | 🎨 Gulli

🎯 Score: 65/100 (🔥HOT)
📊 Ehtimol: 72% (high)
💰 Daromad: 2 000 000 – 3 500 000 UZS
💵 Eng yaxshi: 2 800 000 UZS
📦 Upsell: yuqori — Premium tekstura + LED RGB

🧠 Xaridor: ⭐ Sifat xaridori (65%)
📞 Strategiya: Premium materiallar afzalligi

🔄 Suhbat: yaxshi (8/10)
📈 Momentum: yuqori

      │
      └── Inline keyboard (5 quick-action buttons):
          ┌──────────┬──────────┬──────────┐
          │   📞     │   📐     │   🔥     │
          │  Call    │  Meas.   │   Hot    │
          ├──────────┼──────────┼──────────┤
          │   ✅     │   ❌     │          │
          │  Deal    │  Lost    │          │
          └──────────┴──────────┴──────────┘
```

### HOT lead inactivity alert

```
🔥 Hot Lead Alert

📋 Lead: #42
👤 Bobur | +998901234567
📍 Qarshi
⏰ Last message: 3h ago

Suggested action:
Bepul o'lchov uchun qo'ng'iroq qiling.

/lead_advice 42
```

---

## 15. STATE DIAGRAM SUMMARY

```
                    ┌─────────┐
         /start ──→ │  IDLE   │
                    └────┬────┘
                         │
            ┌────────────┼────────────────┐
            ▼            ▼                ▼
      ┌──────────┐ ┌──────────┐    ┌───────────┐
      │ BROWSING │ │CALCULATING│    │ AI CHATTING│
      │ (catalog)│ │ (pricing) │    │(free-text) │
      └────┬─────┘ └────┬─────┘    └─────┬─────┘
           │             │                │
           └──────┬──────┘                │
                  ▼                       │
           ┌───────────┐                  │
           │ ORDERING   │◄────────────────┘
           │ (form flow)│
           └─────┬─────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
  ┌──────────┐ ┌────┐ ┌──────┐
  │CONTACTED │ │DEAL│ │ LOST │
  │(operator)│ │(won)│ │(exit)│
  └──────────┘ └────┘ └──────┘
```

### FSM States (AiSupportStates)

| State | Description | Entry Condition |
|-------|-------------|-----------------|
| `waiting_for_name` | Collecting user's name | First AI interaction, no name in memory |
| `waiting_for_ai_question` | Active AI conversation | Name collected, free-text mode |
| `waiting_for_district` | Collecting district | After price calc or catalog follow-up |
| `waiting_for_phone` | Collecting phone number | After district confirmed, ready to order |
| `waiting_photo` | Waiting for room photo | User triggered photo funnel |
| `waiting_room` | Waiting for room type | After photo received |
| `waiting_area_photo` | Waiting for area in photo flow | After room type detected |

---

## 16. ROUTER PRIORITY

Router registration order in `apps/bot/main.py` determines handler priority:

```
Dispatcher
├── admin_router        (1st — role-gated admin commands)
├── callbacks_router    (2nd — all inline keyboard callbacks)
│   ├── lead_callbacks
│   ├── kanban_callbacks       (kanban:*)
│   ├── lead_status            (lead:{id}:status:*)
│   ├── cta_callbacks          (cta:*)
│   ├── sales_closer_callbacks (closer:*)
│   ├── operator_callbacks     (op:*)
│   ├── pipeline_callbacks
│   ├── payment_callbacks
│   └── package_callbacks      (pkg:admin:*)
├── group_router        (3rd — group events)
│   ├── group_admin            (/admin + gs: callbacks)
│   ├── group_start            (/start + /menu in groups)
│   ├── admin_group_tracker    (my_chat_member)
│   ├── welcome                (chat_member join)
│   └── member_status          (my_chat_member log)
├── private_router      (4th — DM conversation flows)
│   ├── support                (/start /help /cancel — FIRST)
│   ├── catalog
│   ├── promotions
│   ├── about
│   ├── packages
│   ├── pricing
│   ├── my_orders
│   ├── payment
│   ├── order
│   ├── operator
│   ├── measurement_lead
│   ├── lead_capture
│   └── ai_support             (free-text catch-all — LAST)
├── moderation_router   (5th — link/flood guard)
└── group_messages      (6th — silent catch-all, always last)
```

**Critical ordering rules**:
- `order_router` before `lead_capture_router` (both handle order-like text)
- `measurement_lead_router` before `ai_support_router` (FSM must win)
- `ai_support_router` always last in private_router (catch-all)
- `moderation_router` after private_router (so menu button taps reach BTN handlers first)
