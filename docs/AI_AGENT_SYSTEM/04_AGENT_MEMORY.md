# 04 — Agent Memory System

> How Madina remembers each customer across sessions, handlers, and channels.

---

## 1. Memory Schema

Every user interacting with the bot accumulates a structured memory profile.
Raw chat text is **never** stored — only extracted structured fields.

```python
AgentMemory {
    user_id: int                     # Telegram user ID (primary key)
    first_name: str                  # From Telegram profile (set on first interaction)
    phone: str | null                # Captured via contact share or free-text regex
    district: str | null             # Qashqadaryo tumanlari (13 districts)
    interested_designs: list[str]    # Catalog items viewed (e.g. ["Gulli", "Mramor"])
    last_calculated_area: float      # m² from latest price calculation
    last_calculated_design: str      # CeilingCategory value used in last calc
    last_calculated_price: int       # UZS result of last calculation
    package_type: str | null         # "standard" | "premium" | "vip"
    lead_score: int                  # 0-100 composite funnel score
    lead_temperature: str            # "hot" (>=60) | "warm" (>=30) | "cold" (<30)
    buyer_type: str                  # price_sensitive | quality_buyer | fast_buyer | research_buyer
    objections: list[str]            # Last 5: qimmat, keyinroq, o'lchov kerak, dizayn tanlayapti
    journey_state: str               # IDLE | BROWSING | CALCULATING | ORDERING | CONTACTED | CONVERTED | LOST
    last_action: str                 # Last event name (e.g. "price_calculated", "catalog_viewed")
    last_action_at: datetime         # UTC timestamp of last action
    last_followup_at: datetime       # When last follow-up message was sent
    followup_count: int              # Total follow-ups sent to this user
    order_form_progress: dict        # {step: value} for abandoned form recovery
    last_objection: str | null       # Most recent objection type
    last_objection_severity: str     # "low" | "medium" | "high"
    last_objection_at: int           # Unix timestamp of last objection
    last_negotiation_tactic: str     # Tactic used in last negotiation response
    last_closing_attempt: str | null # Last closing action attempted
    last_closing_at: int | null      # Unix timestamp of last close attempt
    phone_captured: bool             # Whether phone number has been collected
    last_user_message: str           # Truncated (200 chars) last user message
    last_fu_type: str | null         # Follow-up type chosen by brain service
    negotiation_escalated: bool      # Whether negotiation was escalated to manager
    created_at: datetime             # First interaction timestamp
    updated_at: datetime             # Last memory write timestamp
}
```

---

## 2. Memory Storage Strategy

### Dual-layer architecture

| Layer | Store | Key / Table | TTL | Purpose |
|-------|-------|-------------|-----|---------|
| **HOT** (real-time) | Redis hash | `ai:memory:{user_id}` | 30 days (`CacheTTL.AI_MEMORY = 2_592_000`) | Fast read/write during active conversation |
| **COLD** (persistent) | PostgreSQL | `ai_user_memory` table | Permanent | Long-term profile, survives Redis eviction |
| **Conversation** | PostgreSQL | `ai_conversations` table | Permanent | Rolling 12-message window + summary |

### Read path

```
1. Redis  →  ai:memory:{user_id}  →  found? return immediately
2. Postgres  →  ai_user_memory WHERE user_id = X  →  found? hydrate Redis, return
3. Neither  →  return empty dict {}
```

Implementation in `apps/bot/handlers/private/ai_memory.py`:

```python
async def _load_ai_memory(user_id: int) -> dict[str, Any]:
    """Load per-user AI memory from Redis. Returns {} on any error."""
    return (await get_redis().get_json(CacheKeys.ai_memory(user_id))) or {}
```

### Write path (write-through)

Every memory update writes to **both** stores simultaneously:

```
Handler event → _save_ai_memory(user_id, memory)
                    ├── Redis SET with 30-day TTL
                    └── PostgreSQL UPSERT (ai_user_memory)
```

Implementation in `apps/bot/handlers/private/ai_memory.py`:

```python
async def _save_ai_memory(user_id: int, memory: dict[str, Any]) -> None:
    """Persist AI memory to Redis with 30-day TTL. Never raises."""
    now = int(time.time())
    if "created_at" not in memory:
        memory["created_at"] = now
    memory["updated_at"] = now
    await get_redis().set_json(CacheKeys.ai_memory(user_id), memory, ttl=CacheTTL.AI_MEMORY)
```

### Additional Redis keys per user

| Key | TTL | Purpose |
|-----|-----|---------|
| `ai:score:{user_id}` | 30 days | Lead score (0-100, INCR-based) |
| `ai:followup_state:{user_id}` | 24 hours | `{first_sent, second_sent, lead_created}` |
| `ai:last_interaction:{user_id}` | 24 hours | Unix timestamp of last AI message |
| `madina:followup_nonce:{user_id}` | 2 hours | Random nonce for follow-up cancellation |
| `madina:catalog_followup:{user_id}` | 24 hours | Dedup flag for catalog follow-up |
| `closer:last:{user_id}` | 10 minutes | Sales closer cooldown |
| `ai:calls:{user_id}` | 25 hours | Daily AI rate limit counter |

---

## 3. Memory Update Triggers

Each handler updates specific fields when relevant events occur.

### Handler-to-field mapping

| Handler File | Event | Fields Updated | Score Delta |
|-------------|-------|----------------|-------------|
| `ai_support.py` | AI question asked | `last_user_message`, `last_action` | - |
| `ai_support.py` | AI response received | `lead_score` (via `_update_lead_ai_scoring`) | - |
| `ai_scoring.py` | Objection detected | `last_objection`, `last_objection_severity`, `last_objection_at` | expensive: +5, trust: +5, compare: +5, delay: -10, angry: -5 |
| `ai_scoring.py` | Negotiation triggered | `last_negotiation_tactic`, `last_negotiation_at`, `negotiation_escalated` | - |
| `ai_detection.py` | Area parsed from text | `area_m2` (via `parse_combo`) | +15 |
| `ai_detection.py` | Design detected | `design_type` | - |
| `ai_detection.py` | District detected | `district` | +10 |
| `ai_pricing_helpers.py` | Price calculated | `price_area`, `price_district`, `price_design` (FSM) | +10 |
| `catalog.py` | Catalog viewed | `interested_designs` | +5 |
| `lead_capture.py` | District submitted | `district` | +10 |
| `lead_capture.py` | Phone shared | `phone_captured = True` | +40 |
| `measurement_lead.py` | Measurement requested | `journey_state = ORDERING` | +25 |
| `order.py` | Order form started | `order_form_progress`, `journey_state = ORDERING` | +25 |
| `order.py` | Order form step done | `order_form_progress[step] = value` | - |
| `order.py` | Order form abandoned | `order_form_progress` (preserved) | - |
| `packages.py` | Package selected | `package_type` | +10 |
| `operator.py` | Operator requested | `journey_state = CONTACTED` | - |
| `ai_followups.py` | Follow-up sent | `followup_count += 1`, `last_followup_at` | - |

### Memory update flow (ai_memory.py)

```python
async def _update_ai_memory_from_interaction(user_id, *, text, fsm_data, first_name):
    memory = await _load_ai_memory(user_id)

    # 1. Name: FSM > Telegram first_name > existing
    # 2. Parse combo: district, area_m2, design_type from text
    # 3. FSM fallbacks: price_district, price_area, price_design
    # 4. Lead score from Redis
    # 5. Last message (truncated 200 chars)

    await _save_ai_memory(user_id, memory)
```

---

## 4. Lead Score System

Numeric score 0-100, stored in Redis as a simple string counter.

### Score deltas by event

| Event | Delta | Source |
|-------|-------|--------|
| Area parsed (m2) | +15 | `ai_support.py` |
| District detected | +10 | `ai_support.py` |
| Price query | +10 | `ai_support.py` |
| Catalog viewed | +5 | `ai_support.py` |
| Measurement requested | +25 | `ai_support.py` |
| Phone shared | +40 | `ai_support.py` |
| Package selected | +10 | `packages.py` |
| Delay objection | -10 | `ai_scoring.py` |
| Angry objection | -5 | `ai_scoring.py` |
| Expensive/trust/compare objection | +5 | `ai_scoring.py` |

### Temperature classification

```python
def classify_score(score: int) -> str:
    if score >= 60: return "hot"    # HOT
    if score >= 30: return "warm"   # WARM
    return "cold"                    # COLD
```

### Score implementation

```python
async def _add_lead_score(user_id: int, delta: int) -> int:
    current = await _get_lead_score(user_id)
    new_score = max(0, min(100, current + delta))  # clamp [0, 100]
    await get_redis().set(CacheKeys.ai_lead_score(user_id), str(new_score), ttl=CacheTTL.AI_LEAD_SCORE)
    return new_score
```

### Severity-adjusted deltas

High-severity objections amplify penalties:
- `high` severity: penalty doubled (e.g., delay -10 becomes -20)
- `medium` severity: penalty x1.5 (e.g., delay -10 becomes -15)
- `low` severity: base delta unchanged

---

## 5. Buyer Type Classification

Four buyer archetypes determined by `core/services/lead_intelligence_service.py`:

| Buyer Type | Signals | Strategy |
|-----------|---------|----------|
| `price_sensitive` | "qimmat" objections, budget mentions, discount requests | Cheaper alternatives, payment plans, value framing |
| `quality_buyer` | Design interest, premium/VIP package, catalog browsing | Premium upsell, material quality, 15-year warranty |
| `fast_buyer` | Quick phone share, measurement request, low question count | Fast-track to order, minimal friction |
| `research_buyer` | Many questions, catalog deep-dive, comparison queries | Detailed specs, social proof, portfolio |

Buyer type is computed using per-type scoring functions and normalized confidence:
```python
confidence = normalized gap between winner and runner-up score (min 0.3)
```

---

## 6. Conversation Context (PostgreSQL)

### ai_conversations table

| Column | Type | Purpose |
|--------|------|---------|
| `user_id` | BIGINT PK | Telegram user ID |
| `last_messages` | JSONB | Rolling window of last 12 messages `[{role, text}]` |
| `summary` | TEXT | GPT-generated 2-4 line conversation summary |
| `lead_temperature` | VARCHAR | Current temperature from AI scoring |
| `closing_confidence` | FLOAT | 0.0-1.0 from AI analysis |
| `updated_at` | TIMESTAMPTZ | Last update time |

### ai_user_memory table

| Column | Type | Purpose |
|--------|------|---------|
| `user_id` | BIGINT PK | Telegram user ID |
| `profile` | JSONB | Structured profile dict (interested_design, last_dimensions, location, turn_count, last_intent) |
| `updated_at` | TIMESTAMPTZ | Last update time |

### Conversation windowing

- `_MAX_MESSAGES = 12` — max stored in DB
- `_HISTORY_TO_SEND = 8` — max passed to OpenAI per call
- `_SUMMARY_EVERY_N_TURNS = 10` — regenerate GPT summary
- `_MAX_REQUEST_TOKENS = 8000` — hard cap on OpenAI prompt
- Older messages are trimmed from the middle (system messages and current user message are never removed)

---

## 7. Memory Integration with Existing System

### Current implementation

The existing Redis AI memory (`CacheKeys.ai_memory`) stores a flat dictionary:

```python
{
    "name": "Bobur",
    "district": "Qarshi",
    "area_m2": 25.0,
    "design_type": "Gulli",
    "lead_score": 45,
    "phone_captured": true,
    "last_user_message": "25 m2 gulli potolok...",
    "last_objection": "expensive",
    "last_objection_severity": "medium",
    "last_objection_at": 1716500000,
    "last_negotiation_tactic": "cheaper_alternative",
    "last_negotiation_at": 1716500100,
    "created_at": 1716400000,
    "updated_at": 1716500100
}
```

### Extension path

To add journey tracking, extend the existing memory dict with new fields:

```python
# New fields (backward-compatible — absent keys default to None/0)
{
    ...existing fields...
    "journey_state": "CALCULATING",
    "interested_designs": ["Gulli", "Mramor"],
    "last_calculated_price": 5000000,
    "order_form_progress": {"step_1": "Bobur", "step_2": "+998901234567"},
    "followup_count": 2,
    "last_followup_at": 1716500500,
    "buyer_type": "quality_buyer",
}
```

### Migration strategy

1. **Read**: `_load_ai_memory()` already returns `{}` for missing keys — new fields auto-default
2. **Write**: `_save_ai_memory()` writes the full dict — new fields are persisted on first update
3. **No schema migration needed**: Redis stores JSON blobs, new fields are additive
4. **DB migration**: PostgreSQL `ai_user_memory.profile` is JSONB — schema-less, additive

---

## 8. Memory-Powered Personalization

### Greeting personalization (`_build_greeting_from_memory`)

```python
# Priority chain:
if phone_captured:
    "Salom yana {name}. Zakazingiz bo'yicha yoki boshqa savol bormi?"
elif district and area:
    "Salom {name}. {district}dagi {area} m2 potolok bo'yicha savolingiz bormi?"
elif district:
    "Salom {name}. {district}dagi xonadoningiz uchun nima kerak?"
else:
    "Salom {name}. Potolok bo'yicha yordam kerakmi?"
```

### Context injection into OpenAI

The `_build_context_block()` function injects user profile into the system prompt:

```
--- FOYDALANUVCHI KONTEKSTI ---
Profil: qiziqayotgan dizayn: Gulli; so'nggi o'lcham: 5x4; joylashuv: Qarshi
Suhbat qisqartmasi: Foydalanuvchi mehmonxona uchun gulli potolok narxini...
Oxirgi CTA turi: price
```

### Admin notification enrichment

Memory fields flow into the admin lead card via `_notify_ai_lead_collected()`:
- Deal probability (score * 0.4 + confidence * 20 + signal bonuses)
- Buyer profile (type + confidence + strategy)
- Revenue estimate (min/best/max range based on area and buyer type)
- Conversation health (engagement score, momentum, risk signals)
- Follow-up decision (brain-driven timing and message type)

---

## 9. Memory Safety Rules

### Data protection

| Rule | Implementation |
|------|---------------|
| No raw message text | Only `last_user_message` stored, truncated to 200 chars |
| Phone numbers masked in logs | `log.warning()` never includes full phone |
| Objection list capped | Keep only last 5 objection entries |
| No PII in Redis keys | Keys use numeric `user_id` only, not names/phones |
| TTL-based auto-expiry | 30-day TTL on all Redis memory keys |
| Sensitive fields | Phone stored only in PostgreSQL leads table (not in Redis memory blob) |

### Memory cleanup

| Condition | Action |
|-----------|--------|
| 30 days no interaction | Redis keys auto-expire (TTL) |
| 90 days no interaction | Scheduled job purges cold PostgreSQL records |
| User blocks bot | `TelegramForbiddenError` → add to `blocked_chats`, skip in broadcasts |
| User says "kerak emas" | Follow-up state reset, no more automated messages |

### Error handling

All memory operations are **non-fatal** (wrapped in try/except):

```python
async def _save_ai_memory(user_id, memory):
    try:
        await get_redis().set_json(...)
    except Exception:
        pass  # never crash the handler
```

---

## 10. Daily AI Stats Counters

Separate from per-user memory, daily aggregate counters track AI performance:

| Counter Key | Field | Description |
|------------|-------|-------------|
| `ai:stats:{date}:users_started` | `users_started` | Unique users who interacted (deduped via NX) |
| `ai:stats:{date}:messages_total` | `messages_total` | Total AI messages processed |
| `ai:stats:{date}:lead_hot` | `lead_hot` | Leads classified as HOT |
| `ai:stats:{date}:lead_warm` | `lead_warm` | Leads classified as WARM |
| `ai:stats:{date}:lead_cold` | `lead_cold` | Leads classified as COLD |
| `ai:stats:{date}:phones_received` | `phones_received` | Phone numbers captured |
| `ai:stats:{date}:orders_started` | `orders_started` | Order forms initiated |

TTL: 48 hours (keeps today + yesterday for daily comparison reports).
