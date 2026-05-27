# AI System

This document describes the AI assistant architecture, intelligence services, and safety mechanisms.

---

## Purpose

The AI assistant "Madina" acts as a virtual sales manager in Telegram DMs. It:
- Answers product questions about stretch ceilings in Uzbek
- Detects purchase intent and captures lead data (phone, area, district)
- Handles objections (price, delay, trust, comparison, anger)
- Scores leads in real-time (0-100)
- Schedules context-aware follow-ups
- Generates admin intelligence cards with deal probability, buyer type, and recommended actions

---

## Message Processing Pipeline

```
User sends free-text message in DM
        │
        ▼
[ai_detection.py] Intent Detection
  ├─ Dimension pair (e.g. "5x4")? → Pricing FSM
  ├─ Single number? → Pricing FSM at width step
  ├─ Measurement keyword? → Measurement flow
  ├─ Catalog keyword? → Catalog link
  ├─ Greeting only? → Greeting + CTA (no OpenAI)
  └─ General question → continue
        │
        ▼
[ai_scoring.py] Health Check
  ├─ Load Redis score
  ├─ Compute conversation health
  └─ Decide: call OpenAI or use template?
        │
        ▼
[ai_memory.py] Load Context
  ├─ Redis: user profile (30-day TTL)
  ├─ DB: ai_conversations (last 12 messages + summary)
  └─ Build dynamic context block
        │
        ▼
[ai_openai.py] OpenAI Call
  ├─ Pre-flight: detect_prompt_injection(user_text)
  ├─ Build messages: [system_prompt, context_block, ...history, user_msg]
  ├─ Token budget: trim if > 8000 tokens
  ├─ Call API: gpt-4o, temp=0.3, max_tokens=512
  ├─ Retry: 3 attempts, 1s base delay
  ├─ Post-flight: sanitize_ai_reply()
  └─ Parse JSON: {intent, reply, lead_temperature, closing_confidence, extracted}
        │
        ▼
[ai_scoring.py] Score Update
  ├─ Detect objections (keyword + fuzzy regex)
  ├─ Apply score deltas to Redis
  ├─ If objection → negotiation engine reply
  └─ Classify: hot/warm/cold
        │
        ▼
[ai_openai.py] Persist
  ├─ Upsert ai_conversations (rolling 12 messages, summary)
  ├─ Upsert ai_memory (profile)
  └─ Every 10 turns: regenerate summary
        │
        ▼
[ai_notifications.py] Async Tasks (fire-and-forget)
  ├─ Update lead AI scoring in DB
  ├─ Build intelligence card (8 services)
  ├─ Send admin notification
  └─ Schedule follow-up
```

---

## AI Services List

### Intelligence Stack (8 pure-function services, no I/O)

| Service | File | Output | Purpose |
|---------|------|--------|---------|
| **Deal Probability** | `shared/utils/deal_probability.py` | 0-100%, confidence level, reasons | Composite signal scoring for deal closure likelihood |
| **Buyer Intelligence** | `core/services/lead_intelligence_service.py` | buyer_type + confidence + strategy | 4-type psychographic classification (price_sensitive, quality, fast, research) |
| **Revenue Predictor** | `core/services/revenue_predictor_service.py` | min/best/max UZS + upsell potential | Revenue range from area, design, buyer type |
| **Negotiation Engine** | `core/services/negotiation_engine_service.py` | tactic + reply + escalation flag | 8-tactic selection for objection handling |
| **Conversation Graph** | `core/services/conversation_memory_graph_service.py` | stage + trend + timeline | 7 decision stages, 4 engagement trends |
| **Follow-up Brain** | `core/services/followup_brain_service.py` | type + delay + message | 6 follow-up types with progressive backoff |
| **Deal Radar** | `core/services/deal_radar_service.py` | bucket + priority score | 5-bucket lead prioritization |
| **Operator Assistant** | `core/services/operator_assistant_service.py` | reply + reason | 4 reply types for human operators |

### Orchestrators

| Service | File | Purpose |
|---------|------|---------|
| **AI Orchestrator** | `core/services/ai_orchestrator_service.py` | Top-level: composes all 8 services into `AIOrchestratorState` |
| **Sales Brain** | `core/services/ai_sales_brain_service.py` | Composes 8 services into `SalesBrainDecision` |
| **Auto Closer** | `core/services/ai_auto_closer_service.py` | Operator close-reply suggestions from SalesBrain output |
| **Conversation Intelligence** | `core/services/conversation_intelligence_service.py` | Health score + signal detection |

### Agent Rule Engine

| Component | File | Purpose |
|-----------|------|---------|
| **Engine** | `core/services/agent/engine.py` | Priority-ordered rule evaluation |
| **Rules** | `core/services/agent/rules.py` | 10 rules: StaleLeadRule, PhoneCapturedRule, ObjectionRule, etc. |
| **Cooldown** | `core/services/agent/cooldown.py` | Redis NX-based deduplication (60s per trigger/user/lead) |
| **Signal Builder** | `core/services/agent/signal_builder.py` | Constructs signal dict from CRM data |

---

## Prompt and Memory Logic

### System Prompt (`apps/bot/ai/system_prompt.py`)

Role: Sales manager "Madina" for stretch ceiling company.

Key rules embedded in prompt:
- Uzbek language only, 3-5 sentences max, 1-2 emojis max
- Only ceiling topic (redirect otherwise)
- NEVER say reserved operator phrases
- NEVER invent user's design choice
- End with question (except for concrete info like warranty)
- Pricing table embedded directly in prompt
- Scoring guidance (hot/warm/cold criteria)
- CTA rotation rules (no repetition)
- Group safety (never ask phone in group)

### Knowledge Base (`shared/knowledge/uz.md`)

Product facts injected into system prompt:
- Company: 6 years experience, 15-year warranty, Qashqadarya region
- Operator contacts and business hours (09:00-20:00)
- Design price table
- FAQ answers (water resistance, smell, cleaning, warranty)
- Objection counters for common pushbacks

### Conversation Memory

**Redis AI Memory** (per user, 30-day TTL):
```
name, district, area_m2, phone_captured, design_type, buyer_type
last_objection, last_objection_severity, last_negotiation_tactic
negotiation_escalated, lead_temperature, closing_confidence
last_user_message (200 chars max), created_at, updated_at
```

**DB Conversation History** (`ai_conversations` table):
```
user_id (PK), last_messages (JSONB, rolling 12), summary
lead_temperature, closing_confidence, updated_at
```

Summary is regenerated every 10 user turns via a separate OpenAI call.

### Context Block (Dynamic Second System Message)

Built per request from profile + summary + last intent. Provides the model with user-specific context without repeating all history.

---

## Lead Scoring

### Score Storage
- Redis key: `ai:score:{user_id}`, TTL 30 days
- Range: 0-100 (clamped)
- Classification: hot (>= 60), warm (30-59), cold (< 30)

### Score Deltas

| Signal | Delta |
|--------|-------|
| Measurement request | +25 |
| Area provided | +15 |
| District provided | +10 |
| Price query | +10 |
| Phone captured | +40 |
| Catalog interest | +5 |
| Delay objection | -10 |
| Price/trust objection | +5 |
| Angry/negative | -5 |

### Objection Detection

5 types detected via keyword frozensets (130+ keywords) + fuzzy regex patterns (20+ patterns):
- `expensive` — price complaints
- `trust` — quality/reliability doubts
- `compare` — competitor comparison
- `delay` — "later", "not now"
- `angry` — negative/hostile language

Each objection has severity scoring (low/medium/high).

---

## Follow-up Logic

### Brain-Driven Scheduling

The `FollowupBrain` service decides:
1. **Whether** to follow up (skip if: cap reached, recently active, cold+cooling+low score)
2. **What type** (6 types: price_reminder, catalog_nudge, measurement_push, soft_reactivation, manager_call_offer, budget_option_offer)
3. **When** (base delay per type + adjustments for temperature, probability, trend, progressive backoff)

### Execution

Follow-ups are processed by `FollowupService` (called from APScheduler every 60s):
1. Query `leads.next_follow_up_at <= now()`
2. For each due lead, run intelligence stack
3. Send reminder card to admin
4. Increment `follow_up_count`
5. Reschedule next follow-up (or clear if cap reached)

### Caps
- `MAX_FOLLOWUP_COUNT = 5` per lead
- Brain-driven rotation prevents same type consecutively
- Progressive backoff: +50% delay per attempt

---

## Prompt Injection Protection

### Pre-flight (Input)

```python
detect_prompt_injection(user_text) -> bool
```

Detects:
- SQL/shell injection patterns
- Roleplay requests ("act as", "pretend")
- Jailbreak attempts ("ignore previous", "reveal system prompt")
- Unauthorized elevation ("unrestricted mode", "DAN")

If detected: return canned refusal, do not call OpenAI.

### Post-flight (Output)

```python
sanitize_ai_reply(reply: str) -> str | None
```

Checks for:
- Leaked system prompt fragments
- Instruction artifacts
- Control characters

If suspicious: return `None`, handler sends canned refusal.

### Input Sanitization

```python
sanitize_user_text_for_prompt(text, max_length, placeholder) -> str
```

- Truncates to `max_length` (300 chars for summary, 200 for notifications)
- Sanitizes for LLM prompt injection
- Returns `placeholder` if blocked

---

## Token Management

| Parameter | Value |
|-----------|-------|
| Model | gpt-4o (configurable via `OPENAI_MODEL`) |
| Temperature | 0.3 |
| Max completion tokens | 512 |
| Max request tokens | 8,000 |
| Chars per token estimate | 3 (conservative for Uzbek) |
| History window | 12 messages in DB, 8 sent to OpenAI |
| Summary regeneration | Every 10 user turns |
| Daily rate limit | 100 messages/user |
| Retry policy | 3 attempts, 1s base delay |
| Retryable errors | APIConnectionError, APITimeoutError, RateLimitError |

### Budget Enforcement

Messages are trimmed oldest-first (never touching system messages or current user message) until total estimated tokens <= 8,000.

---

## Monitoring

### Prometheus Metrics

- `openai_requests_total[model, status]` — success/error count
- `openai_request_duration_seconds[model]` — latency histogram
- `openai_tokens_prompt_total[model]` — prompt token count
- `openai_tokens_completion_total[model]` — completion token count

### Daily AI Stats (Redis)

Per-day metrics (auto-expire 48h):
- `users_started` (unique users who messaged AI)
- `messages_total`
- `lead_hot`, `lead_warm`, `lead_cold` (classification counts)
- `phones_received`, `orders_started`

---

## What Must Be Moved for SaaS Readiness

| Current Location | Issue | Target Location |
|-----------------|-------|-----------------|
| `apps/bot/ai/system_prompt.py` — `sanitize_*` functions | Core services import from apps layer | `shared/utils/sanitize.py` |
| `apps/bot/handlers/private/ai_openai.py` — `_get_client()`, `_record_usage()` | Core services import from apps layer | `core/services/ai_client.py` or `infrastructure/ai/openai_client.py` |
| System prompt text | Hardcoded in Python file | DB-backed or config file per tenant |
| Knowledge base (`shared/knowledge/uz.md`) | Static file, single language | DB-backed knowledge entities |
| Pricing constants in system prompt | Duplicated from `pricing_service.py` | Single source: `shared/constants/pricing.py` |
| AI memory (Redis only) | No API access to memory data | Add API endpoints for memory inspection |
| Token usage | Not tracked per user/tenant | Add per-tenant cost attribution |
