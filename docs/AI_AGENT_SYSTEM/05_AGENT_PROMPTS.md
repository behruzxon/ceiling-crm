# 05 — Agent Prompts (Uzbek)

> All AI agent prompts in Uzbek language. Each prompt is natural, conversational,
> short (2-4 sentences max), includes 1-2 emojis, ends with CTA or question,
> and is personalized with template variables where applicable.

---

## Template Variables

| Variable | Source | Example |
|----------|--------|---------|
| `{ism}` | `memory.name` or `from_user.first_name` | Bobur |
| `{design}` | `memory.design_type` or `fsm_data.price_design` | Gulli |
| `{narx}` | Formatted price in UZS | 5 000 000 |
| `{maydon}` | `memory.area_m2` | 25 |
| `{district}` | `memory.district` | Qarshi |
| `{temperature}` | `classify_score(score)` | hot / warm / cold |
| `{username}` | `from_user.username` | @bobur_uz |
| `{phone}` | Captured phone number | +998901234567 |
| `{remaining}` | Steps left in order form | 2 |
| `{journey_state}` | Current journey state | CALCULATING |
| `{last_action}` | Last event name | price_calculated |
| `{score}` | Numeric lead score | 65 |

---

## 1. MAIN SALES ASSISTANT PROMPT (System Prompt Extension)

Used when Madina operates in follow-up mode with accumulated context.

```
Sen Madina — VASHPOTOLOK savdo yordamchisi. Mijoz {journey_state} holatida.
Uning so'nggi harakati: {last_action}. Lead temperaturasi: {temperature}.
Maqsad: mijozni keyingi qadamga olib borish.
Qisqa, tabiiy, do'stona javob ber. Haddan oshma.
```

**Core system prompt** (from `apps/bot/ai/system_prompt.py`):

```
Sen "VASHPOTOLOK" kompaniyasining tajribali savdo menejeri va botdagi
yordamchisisan (ism: Madina). Kompaniya Qashqadaryo viloyatida natijnoy
patalok o'rnatish bilan shug'ullanadi.

ASOSIY QOIDALAR:
- Faqat o'zbek tilida javob ber.
- 3-5 jumladan oshirma.
- 1-2 ta mos emoji ishlat (haddan oshma).
- Faqat natijnoy patalok mavzusida gapir.
- Odatda javobni savol bilan tugat.
```

---

## 2. CATALOG FOLLOW-UP PROMPT

**Trigger**: 5-10 minutes after catalog button was sent, user is silent.
**Dedup**: `CacheKeys.catalog_followup_sent(user_id)`, TTL 24 hours.
**Skip conditions**: User is in phone/district/photo collection state, or active in order/pricing FSM.

### Message

```
Ko'rib chiqdizmi? 😊
Xohlasangiz, bepul o'lchov uchun zakaz qabul qilib qo'yaymi?

Qaysi tumandasiz va taxminiy maydon nechchi m²?
```

### Personalized variant (when name + design known)

```
Salom {ism} 😊 Katalogdagi qaysi model sizga yoqdi?
Xonangiz kvadratini yozsangiz, taxminiy narxni 1 daqiqada hisoblab beraman.
```

### Buttons

```
[💰 Narx hisoblash]  [📚 Yana katalog]
```

**Implementation**: `apps/bot/handlers/private/ai_followups.py` -> `_catalog_followup_task()`

---

## 3. PRICE FOLLOW-UP PROMPT

**Trigger**: 10 minutes after price calculation, user has not continued.
**Condition**: User has `price_area` in FSM but no phone captured.

### Message

```
💰 {design} uchun {maydon}m² narxi — {narx} so'm.
Hozir buyurtma bersangiz bepul o'lchov + 15 yil kafolat!
Buyurtma berasizmi? 👇
```

### Buttons

```
[🛒 Buyurtma berish]  [📞 Operator]  [🔄 Boshqa dizayn]
```

---

## 4. ABANDONED FORM PROMPT

**Trigger**: 10 minutes after order form was abandoned mid-flow.
**Condition**: `order_form_progress` has at least one step completed.

### Message

```
📝 {ism}, buyurtmangiz yarim qoldi!
Davom etasizmi? Atigi {remaining} qadam qoldi 😊
```

### Buttons

```
[✅ Davom etish]  [🎁 Paketlar]  [❌ Kerak emas]
```

---

## 5. PHONE REMINDER PROMPT

**Trigger**: 15 minutes after price calculation, phone not yet captured.
**Condition**: `phone_captured == False` and `price_area` exists.

### Message

```
📞 {ism}, narx hisoblangandan keyin usta chaqirish uchun telefon
raqamingiz kerak. Raqamni yuboring — biz sizga eng qulay vaqtda
qo'ng'iroq qilamiz 😊
```

### Buttons

```
[📱 Raqam yuborish]  [⏭ Keyinroq]
```

---

## 6. 24H SOFT REMINDER

**Trigger**: `check_inactive_leads` job, 24 hours after last interaction.
**Dedup**: `follow_up_count >= 1` check (skip if already reminded).
**Business hours**: Suppressed during off-hours (`is_off_hours()`).

### Message

```
Assalomu alaykum {ism}! 😊
Natijnoy patalok haqida savollaringiz bormi?
Bepul o'lchov xizmati davom etmoqda.
Yozing, yordam beraman!
```

### Buttons

```
[💰 Narx]  [📚 Katalog]  [📐 Bepul o'lchov]
```

---

## 7. 72H FINAL OFFER

**Trigger**: `check_inactive_leads` job, 72 hours after last interaction.
**Dedup**: `follow_up_count >= 2` check.
**Escalation**: After this message, 7-day inactivity marks lead as LOST.

### Message

```
Salom {ism}! 🎁
Bu hafta {district} tumanida o'rnatish rejalashtirilgan.
Hali ulgurasiz! Maxsus narx olish uchun hozir yozing.
```

### Buttons

```
[📞 Bog'lanish]  [💰 Narx]  [❌ Kerak emas]
```

---

## 8. OBJECTION HANDLING PROMPTS

Detected by keyword matching (130+ keywords) + fuzzy regex patterns in
`apps/bot/handlers/private/ai_scoring.py`.

### 8.1 "Qimmat" (expensive)

**Detection**: `_OBJECTION_EXPENSIVE_KW` — qimmat, narx baland, pul yo'q, дорого, etc.
**Score delta**: +5 (engagement signal)

```
Narx balandroq ko'rinishi mumkin, lekin biz sifatli material va toza montaj
qilamiz, 15 yil kafolat bor. Natijnoy potolok uzoq xizmat qiladi — keyin
qayta xarajat bo'lmaydi.
Xohlasangiz, maydon (m²) va tumanni aytsangiz aniq hisoblab beraman 🙂
```

**When negotiation engine activates** (price_sensitive buyer):

```
Tushunaman! Arzonroq variantlar ham bor. Masalan, adnatonniy turi
80 000 so'm/m² — {maydon}m² uchun atigi {arzon_narx} so'm.
Ko'rsatayinmi? 🙂
```

### 8.2 "Keyinroq" (delay)

**Detection**: `_OBJECTION_DELAY_KW` — keyinroq, hozir emas, o'ylab ko'raman, потом, etc.
**Score delta**: -10 (disengagement signal)
**Severity-adjusted follow-up delay**: HOT low=+6h, HOT high=+12h, WARM=+24h, COLD=+48h

```
Mayli 🙂 Shoshilmasangiz ham bo'ladi. Men hozir sizga mos variantlarni
tayyorlab qo'yaman, keyin tayyor bo'lsangiz davom ettiramiz.
Qaysi xonaga kerak va taxminiy maydon nechchi m²?
```

### 8.3 "Ishonch yo'q" (trust)

**Detection**: `_OBJECTION_TRUST_KW` — ishonmayman, kafolat bormi, aldayapsiz, не верю, etc.
**Score delta**: +5 (engagement signal)

```
Tushunaman. Biz rasmiy ishlaymiz: sifatli material, toza montaj va
15 yil kafolat bor. Xohlasangiz, katalogimizdan real ishlarimizni
ko'rsataman. Qaysi xonaga kerak va taxminiy maydon nechchi m²?
```

### 8.4 "Solishtirish" (compare)

**Detection**: `_OBJECTION_COMPARE_KW` — boshqada arzon, skidka, narxni tushir, дешевле, etc.
**Score delta**: +5

```
To'g'ri, bozorda turli narxlar bor. Bizda farq — sifat, montaj
tozaligi va kafolat. Xohlasangiz, sizning maydon va tumanga qarab
byudjet yoki premium variantni tavsiya qilaman 🙂 Maydon nechchi m²?
```

### 8.5 "G'azablangan" (angry)

**Detection**: `_OBJECTION_ANGRY_KW` — kerakmas, bezor, jonga tegdi, достали, etc.
**Score delta**: -5

```
Tushundim 🙂 Sizni bezovta qilmayman. Aniq yordam kerak bo'lsa yozing:
narx hisoblab beraymi yoki katalog yuboraymi? Qaysi xonaga kerak?
```

### 8.6 "O'lchov kerak" (measurement request)

**Detection**: `_MEASUREMENT_TRIGGERS` — o'lchov kerak, usta chaqir, zakaz qil, buyurtma, etc.
**Handled by**: Measurement lead flow (not objection system)

```
Ajoyib! Bepul o'lchov xizmati bor 🙂
Qaysi tuman? Usta eng yaqin vaqtda keladi.
```

### 8.7 "Dizayn tanlayapti" (browsing designs)

**Detection**: `_CATALOG_TRIGGERS` — katalog, dizayn, variant, rasm, ko'rsat, etc.
**Handled by**: Catalog flow with room/design context detection

```
Sizga qaysi uslub yoqadi? Zamonaviy, klassik yoki original?
Katalogdan ko'rsataman 😊
```

---

## 9. OPERATOR ESCALATION PROMPT

Sent to admin group when operator handoff is requested or negotiation escalates.

### Admin group message

```
👔 Operator kerak!

Mijoz: {ism} (@{username})
📞 {phone}
📍 {district}
💰 Narx: {narx}
🔥 Status: {temperature}
🎯 Score: {score}/100

So'nggi: {last_action}
💬 "{last_user_message}"
```

### HOT lead objection alert (real-time, deduped 2h)

```
🔥 HOT Lead Objection

📋 Lead: #{lead_id}
🎯 Score: {score}/100
🚫 Type: PRICE
🔴 Severity: HIGH
💬 Message: "{user_message}"

Suggested tactic: {tactic_label}
```

---

## 10. ADMIN SUMMARY PROMPT

### New lead notification card

```
🆕 Yangi lid

📋 Lead #{lead_id}
👤 {ism} (@{username})
📞 {phone}
📍 {district}
📏 Maydon: {maydon} m²
🎨 Dizayn: {design}

🎯 Score: {score}/100 ({temperature_badge})
📊 Ehtimol: {deal_probability}% ({confidence_level})
💰 Daromad: {revenue_min} - {revenue_max} UZS
💵 Eng yaxshi: {revenue_best} UZS
📦 Upsell: {upsell_level}

🧠 Xaridor: {buyer_type_badge} ({buyer_confidence}%)
📞 Strategiya: {buyer_strategy}

🔄 Suhbat: {conversation_health}
📈 Momentum: {momentum}
```

### Daily stats summary

```
📊 AI Kunlik hisobot ({date})

👥 Foydalanuvchilar: {users_started}
💬 Xabarlar: {messages_total}
🔥 HOT: {lead_hot} | 🟡 WARM: {lead_warm} | ❄️ COLD: {lead_cold}
📞 Telefon olindi: {phones_received}
🛒 Zakaz boshlangan: {orders_started}
```

---

## 11. STOP ACKNOWLEDGMENT PROMPTS

### User says "kerak emas" / stops

```
Tushunaman! Fikringiz o'zgarsa, istalgan vaqt yozing.
Yaxshi kun! 😊
```

**Action**: Reset follow-up state, cancel all pending follow-ups.

### User successfully orders

No follow-up message sent. Order confirmation:

```
✅ Buyurtmangiz qabul qilindi!
Operator tez orada bog'lanadi ☎️
```

**Action**: Mark `journey_state = CONVERTED`, clear `next_follow_up_at`.

### User contacts operator

```
Operator tez orada bog'lanadi! ☎️
```

**Action**: Mark `journey_state = CONTACTED`, send admin notification with full lead context.

---

## 12. AI INTERACTION FOLLOW-UP REMINDERS

Two-stage delayed follow-up after any AI interaction. Managed by
`apps/bot/handlers/private/ai_followups.py` -> `_ai_followup_task()`.

### Reminder #1 (10 minutes after last interaction)

```
Yordam kerakmi? 🙂

Agar xohlasangiz:
📏 Xona maydonini yozing
yoki
📍 Tumaningizni yozing

Men sizga aniq narxni hisoblab beraman.
```

### Reminder #2 (60 minutes after last interaction, 50 min after Reminder #1)

```
Agar xohlasangiz bepul o'lchov xizmatimiz ham bor 🙂

Ustamiz kelib aniq narxni aytib beradi.
Zakaz qoldirish uchun telefon raqamingizni yozishingiz mumkin.
```

### Cancellation conditions

Follow-up is cancelled if any of these are true:
- User sent a new message (nonce changed)
- User entered phone/district/photo collection state
- Lead was already created
- Nonce expired (2 hours of total inactivity)

---

## 13. SMART CLOSING CTA

Dynamic single-question CTA based on missing funnel data.

```python
async def _smart_closing_cta(state: FSMContext) -> str:
    if not fsm_data.get("price_area"):
        return "Taxminan xonangiz nechchi m²? 🙂"
    if not fsm_data.get("price_district"):
        return "Qaysi tumandasiz? 📍"
    return "Telefon raqamingizni yuboring, mutaxassisimiz bog'lansin 📞"
```

---

## 14. NEUTRAL / GENERIC RESPONSES

### Greeting response

```
Salom! 🙂
Narx hisoblashmi, katalog ko'rishmi yoki bepul o'lchov kerakmi?
```

### Generic confirmation ("zo'r", "ok", "ha", "rahmat")

```
Tushunarli 🙂
Narx hisoblaymizmi, katalog ko'ramizmi yoki bepul o'lchov kerakmi?
```

### Photo funnel follow-up (7 minutes)

```
Ko'rib chiqdizmi? 🙂
Xohlasangiz, bepul o'lchov uchun ustani yuborib qo'yaman.
Zakaz qabul qilaymi?

Qaysi tumandasiz?
```

---

## 15. PROMPT SAFETY

### Prompt injection firewall

All user text passes through `detect_prompt_injection()` before reaching OpenAI:
- Blocks instruction override attempts
- Blocks system prompt extraction requests
- Blocks role-play manipulation

### Output sanitization

AI responses pass through `sanitize_ai_reply()`:
- Blocks system prompt leaks
- Blocks responses containing injection markers

### Refusal response

```python
INJECTION_REFUSAL = {
    "reply": "Kechirasiz, bu savolga javob bera olmayman. "
             "Natijnoy patalok haqida yordam beraymi? 🙂",
    "intent": "blocked",
}
```
