# 145 — Sales Dialogue Manager: Design & Implementation

> **Status:** Pure service + tests implemented. **NOT wired into the live bot.**
> Gated behind `SALES_DIALOGUE_MANAGER_ENABLED` (**default `False`**). No
> production behaviour changed. Nothing pushed, deployed, or enabled.
>
> **Service:** `core/services/sales_dialogue_manager_service.py`
> **Tests:** `tests/unit/services/test_sales_dialogue_manager_service.py` (508),
> `tests/simulation/agent/test_sales_dialogue_conversations.py` (65)
> **Flag:** `shared/config/settings.py` → `BusinessSettings.sales_dialogue_manager_enabled`

---

## 1. Why routing is not enough

The current bot (torture-tested at **96/100** routing — see report 144) is excellent
at **classifying a single message** and firing the right branch. But it is a *router*,
not an *agent*:

| Router (today) | Agent (this layer) |
|---|---|
| Classifies one message in isolation | Tracks a **conversation** and what's known so far |
| Each branch hardcodes its own question | A single **next-best-question** planner |
| No unified "what's missing?" view | Explicit `MissingInfo` across design/area/district/phone |
| No measure of how close to an order | **Order-readiness score** 0-100 |
| Can re-ask a question already answered | Remembers answers; never re-asks needlessly |
| Facts scattered across 3 stores (FSM, 2× Redis, DB) | One merged `CustomerConversationFacts` view |

The router answers *"what did they just say?"*. The dialogue manager answers
*"given everything they've told me, what is the one best thing to say next to move
this toward an order — without overpromising?"*

---

## 2. The new sales-dialogue model

A single **pure** function per turn — no I/O, no LLM:

```
plan_turn(text, state_data, previous_facts)
    → extract_facts()      # what we know now (merged + sticky)
    → compute_missing_info # what's still needed for an order
    → decide()             # the one best next action (fixed priority)
    → render_message()     # warm, short, Uzbek-Latin reply
    = SalesDialoguePlan(facts, missing, decision, reply_text, questions_asked)
```

It **reuses** the proven detectors (`parse_combo`, `detect_objection_full`, `_is_*`,
`resolve_catalog_link`, `PriceCalculatorService`, `detect_prompt_injection`,
`is_stop_signal`) — it does **not** re-implement price/catalog/operator/order logic.

### Dataclasses
- `CustomerConversationFacts` — all spec fields (design_key, area_m2, room_type,
  district, phone_present, wants_*, has_objection, objection_type, warranty_question,
  stop_signal, last_user_message, conversation_stage, lead_temperature,
  order_readiness_score) + internal helpers (catalog_ambiguous/explicit, safety_risk).
- `MissingInfo` — tuple of still-unknown order fields.
- `SalesDialogueDecision` — intent, confidence, should_answer, should_ask_question,
  question_text, next_action, reason, order_readiness_score, missing_fields, safety_note.
- `SalesDialogueQuestion` — a single field-collecting question.
- `SalesDialoguePlan` — the per-turn bundle.

### Decision priority (fixed, deterministic)
```
1. stop_signal          → polite_stop        (always wins)
2. safety / injection   → safety_block        (always wins)
3. explicit operator    → create_handoff
4. measurement/order    → ask_phone → ask_district → offer_measurement
5. price intent         → ask_area / ask_design / answer_price
6. warranty/quality     → answer_warranty (+ soft next question)
7. objection            → handle_objection (calm)
8. catalog              → send_catalog / clarify(if ambiguous)
9. room only            → ask_area (move toward price)
10. unclear/nonsense    → clarify (one simple question)
```

Price is checked before catalog/warranty (so `gulli nech pul` → price, not catalog);
warranty is checked before objection (so `kafolat bormi` → the informative FAQ, not a
rebuttal). All 17 spec rules are encoded; see the docstring + tests.

---

## 3. Memory facts (Phase 3 adapter)

`extract_facts(text, state_data, previous_facts)` merges three sources, with the
current message winning:

- **Sticky slots** (carry forward): `design_key, area_m2, room_type, district,
  phone_present`. So `"gulli nech pul"` → `"20"` remembers `gulli` and prices it.
- **Intent flags** (current message): `wants_price/catalog/measurement/operator,
  has_objection, warranty_question, stop_signal`.
- **Sticky-flow continuation:** a bare fact-answer (a phone, a district, a design name)
  with no intent of its own *inherits the active flow* — so a phone given after
  `kelinglar` continues to `ask_district`, and a design name given after an
  `ask_design` prompt continues to `answer_price` (not mis-read as a catalog request).

It accepts `previous_facts` as a `CustomerConversationFacts`, a `dict`, or `None`, so the
integration can persist facts in Redis AI-memory and rehydrate them.

Worked examples (all verified by tests):

| Turn | Facts after | Decision |
|---|---|---|
| `gulli nech pul` | design=gulli, wants_price | **ask_area** |
| `20` (prev gulli) | design=gulli, area=20 | **answer_price** |
| `zal uchun` | room=mehmonxona | **ask_area** (room-aware) |
| `kelinglar` | wants_measurement | **ask_phone** |
| `998901234567` (prev measure) | phone=True | **ask_district** |
| `Qarshidan` (prev phone+measure) | district=Qarshi | **offer_measurement** |

---

## 4. Missing-info & order-readiness

`compute_missing_info(facts)` → the order-relevant fields still unknown
(`design_key, area_m2, district, phone_present`; **room is not required**).

`compute_order_readiness(facts)` → 0-100, **monotonically increasing** as facts
accumulate:

| Fact | Weight |
|---|---:|
| phone_present | 30 |
| area_m2 | 25 |
| design_key | 20 |
| district | 15 |
| room_type | 10 |
| **all present** | **100** |

Phone is the heaviest signal (it's the conversion gate). `lead_temperature` is derived:
`hot` (phone or ≥60), `warm` (≥30 or price/measurement intent), else `cold`.

---

## 5. Human-like response rules (Phase 4)

Every reply is built deterministically (no LLM) to be:
- **short** (< 600 chars; clarify < 200), **warm**, **Uzbek Latin only**;
- **one primary question per turn** (`questions_asked ≤ 1`, enforced by tests);
- **fact-aware** — uses the known design/room/area (`"Gulli bo'yicha hisoblab beraman 😊
  Xonangiz taxminan nechchi m²?"`);
- **soft CTA**, light emoji, **never** robotic (`"Intent: price. Missing field: area"`).

The price answer **delegates to `PriceCalculatorService`** (single source of truth) so it
shows a real *taxminiy* estimate that always says *"Yakuniy narx o'lchovdan keyin
aniqlanadi"* — never a final number.

Style contrast (from the spec):

> ✅ `"Zal uchun yordam beraman 😊 Maydoni taxminan nechchi m²? Shunga qarab taxminiy narxni aytaman."`
> ❌ `"Zal uchun quyidagi variantlar mavjud: …"` (long list)

---

## 6. Safety guardrails

- **Stop always wins; safety/injection always wins** (rules 1–2).
- Injection → `safety_block` with a topic-redirect reply that contains no secret.
- **No route can emit** a token / DB URL / system prompt / final price / fake ETA /
  `100%` / `bugun·darhol·hozir` time promise. A reply-scanning invariant runs over the
  whole message corpus in both test files (`_FORBIDDEN`, `_SECRET_MARKERS`).
- Price answers are explicitly *taxminiy*; operator/measurement replies promise **no
  time** ("mutaxassisimiz bog'lanadi", never "bugun/tez orada").

---

## 7. Integration plan (NOT done this pass — proposal only)

**Default OFF.** The flag `SALES_DIALOGUE_MANAGER_ENABLED` already exists
(`default=False`), and **nothing reads it yet**, so live behaviour is unchanged.

Recommended phased rollout:

1. **Log-only (shadow).** In `handle_ai_question` / `handle_ai_message`
   (`apps/bot/handlers/private/ai_support.py`), *before* the existing branch tree, call
   `plan_turn(text, fsm_data, ai_memory_facts)` and **only log** the decision +
   readiness (no behaviour change). Compare against what the live branches actually did.
   Gate the whole block on `settings.business.sales_dialogue_manager_enabled`.
2. **Question-only assist.** When ON, let the manager supply the *next question text*
   for the existing ask branches (price/measurement) so phrasing is fact-aware and
   single-question — still using the existing flows for side-effects.
3. **Full planner.** Let the manager choose the action for the clarify/fallback cases
   that currently go straight to OpenAI, reducing LLM dependence for the 7 hard intents.

Hard constraints for any phase: **no live OpenAI in tests**, the flag stays `False` in
production until explicitly approved, and the manager never bypasses the real FSM for
lead creation / measurement booking (it *decides*; the existing handlers *execute*).

Persistence: store `facts.to_dict()` in the existing Redis AI-memory blob under a
`dialogue_facts` key; rehydrate as `previous_facts` next turn.

---

## 8. Test results

| Suite | Tests | Result |
|---|---:|:--|
| `test_sales_dialogue_manager_service.py` (unit) | **508** | ✅ pass |
| `test_sales_dialogue_conversations.py` (multi-turn) | **65** | ✅ pass |
| `tests/simulation/agent` (whole) | 262 | ✅ pass |
| `tests/unit` (whole) | 7,706 (+1 skipped) | ✅ pass |
| `ruff check .` | — | ✅ clean |
| `black --check core apps/bot shared tests` | 603 files | ✅ clean |

Coverage highlights: every decision rule; the 17 spec rules; fact extraction (incl.
sticky carry-forward and the room/design disambiguation); missing-info; monotonic
readiness; one-question invariant; no-final-price / no-100% / no-ETA / no-secret /
Uzbek-Latin invariants over a 40-message corpus; the 10 named multi-turn flows; 45
generated conversations; stop-after-any-opener; and the flag-default-False guard.

---

## 9. Limitations (honest)

- **Inherited detector gaps** (from report 144, pinned in `TestKnownInheritedGaps`):
  - `"necha pul"` is not a price keyword → `"<design> necha pul"` routes to catalog.
  - Cyrillic `"гули"` (single-л) isn't in the design map (`"гулли"` is).
  These belong to the shared detector layer (root cause R1), **not** this service, and
  were deliberately not changed here (out of scope; would touch routing).
- **The reply text is deterministic, not generative.** It is warm and on-brand but not
  as fluid as GPT-4o for open-ended chat. The manager is meant to own the **7 hard
  intents** and hand genuinely open conversation to the LLM.
- **No sentiment/aggression detector** — hostile messages are routed by their topic word
  or to clarify/LLM (calm, but not explicitly de-escalating).
- **Stop is still exact-match** (inherited `is_stop_signal` limit): `"kerak emas."` with
  punctuation isn't caught. Tracked as report-144 R3.
- Not wired in; no live A/B data yet.

---

## 10. Next sprint

1. **Wire the shadow (log-only) integration** behind the flag and capture a week of
   decision-vs-live comparisons (no behaviour change).
2. **Fix the inherited detector gaps** R1/R3 (`necha pul`, `гули`, robust stop) in the
   shared layer — this lifts both the router (report 144) and this manager.
3. **Persist `dialogue_facts`** in Redis AI-memory and rehydrate per turn.
4. Once shadow data confirms parity, enable **question-only assist** for the price and
   measurement flows.

> No code was wired, no flag enabled, nothing committed. Awaiting approval before any
> integration step.
