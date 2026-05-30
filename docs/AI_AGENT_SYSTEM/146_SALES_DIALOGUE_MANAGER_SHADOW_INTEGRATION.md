# 146 — Sales Dialogue Manager: Shadow / LOG-ONLY Integration

> **Status:** Shadow integration implemented and tested. **Default OFF.** No
> customer-facing behaviour changed. Nothing pushed, deployed, or enabled.
>
> **Flag:** `SALES_DIALOGUE_MANAGER_SHADOW_ENABLED` (default `False`)
> **Helper:** `apps/bot/handlers/private/sales_dialogue_shadow.py`
> **Wired in:** `apps/bot/handlers/private/ai_support.py` (`handle_ai_question`, `handle_ai_message`)
> **Tests:** `tests/unit/bot/test_sales_dialogue_shadow_integration.py` (76)
> **Builds on:** report 145 (the pure planner).

---

## 1. What shadow mode does

When `SALES_DIALOGUE_MANAGER_SHADOW_ENABLED=true`, every message that reaches the two
AI handlers (`handle_ai_question`, `handle_ai_message`) triggers — **in addition to the
normal live flow** — a single fire-and-forget call to
`maybe_log_sales_dialogue_shadow(...)`. That helper:

1. Calls the pure planner `plan_turn(text, state_data, None)` (report 145).
2. **Logs one sanitized line** (`event="sales_dialogue_shadow_decision"`) with the
   planner's decision.
3. Returns. **No reply is sent to the customer.**

This lets us compare what the Sales Dialogue Manager *would* decide against what the live
router *actually* did — on real traffic — with zero risk, before ever letting it answer.

## 2. What shadow mode does NOT do

- ❌ Does **not** produce or alter any customer-facing reply.
- ❌ Does **not** mutate the database.
- ❌ Does **not** mutate FSM state (the helper receives a **dict copy**, never the state object).
- ❌ Does **not** call Telegram (no `bot`/`message` param — structurally impossible).
- ❌ Does **not** call OpenAI (the planner is pure/deterministic).
- ❌ Does **not** add latency to the live path (runs inside `asyncio.create_task`, and the
  whole block is skipped entirely when the flag is off).

## 3. Flags

| Flag | Default | Purpose |
|---|---|---|
| `SALES_DIALOGUE_MANAGER_SHADOW_ENABLED` | **`false`** | Turns on shadow/log-only decision logging. |
| `SALES_DIALOGUE_MANAGER_ENABLED` | `false` | (From report 145) reserved for a future *active* mode; still unused. |

Both default `False` and are pinned by tests
(`TestFlagDefault`, `test_shadow_flag_declared_default_false`).

## 4. Default-OFF behaviour

With the flag off (the default), the wired block is:

```python
if get_settings().business.sales_dialogue_manager_shadow_enabled:   # False → skip
    ...
```

The condition short-circuits → **no `state.get_data()`, no planner call, no log, no task**.
The handler runs **exactly** as before. `TestGating.test_flag_off_does_nothing` and
`TestLiveHandlerUnchanged` pin this.

## 5. Logged fields

One structured log line per message (when ON):

| Field | Example | Notes |
|---|---|---|
| `event` | `sales_dialogue_shadow_decision` | — |
| `user_id` | `42` | Raw, to match existing handler-log convention (aids correlation). |
| `chat_id` | `*****6789` | **Masked** to last 4. |
| `live_route` | `pre_route` | Where in the live flow we sampled (top-level for now). |
| `sdm_intent` | `price` | Planner intent. |
| `sdm_next_action` | `ask_area` | Planner's chosen action. |
| `sdm_confidence` | `0.85` | Rounded to 2 dp. |
| `order_readiness_score` | `20` | 0-100. |
| `missing_fields` | `["area_m2","district","phone_present"]` | Field **names** only. |
| `reason` | `price_needs_area` | Truncated to 60 chars. |
| `safety_note` | `injection_blocked_no_leak` | Truncated to 60 chars. |
| `preview` | `gulli nech pul` | **Redacted**, ≤120 chars. |

## 6. Redaction rules

`_safe_preview(text)` redacts before logging, in this order:
- OpenAI keys (`sk-…`) → `[redacted_key]`
- `Bearer …` → `[redacted_bearer]`
- Telegram bot tokens (`123456789:AA…`) → `[redacted_bot_token]`
- `postgres://…` / `redis://…` → `[redacted_db_url]` / `[redacted_redis_url]`
- markers `BOT_TOKEN` / `OPENAI` / `DATABASE_URL` → `[redacted_marker]`
- **phone-like digit runs (≥7 digits)** → `[redacted_phone]`
- then truncate to 120 chars, newlines collapsed.

`_mask_id(chat_id)` masks all but the last 4 chars. The full raw message is **never**
logged; only the redacted preview. A phone in FSM state (`price_phone`) is never echoed.
`TestNoLeakInLogs` asserts no raw phone/token/key appears in any logged value across a
corpus of leak-bait inputs.

## 7. Safety guarantees

- **Stop & safety still win** inside the planner; but shadow never acts on them — it only logs.
- **Exception-safe:** the helper wraps everything in `try/except` and degrades to a single
  `log.warning("sales_dialogue_shadow_failed")` — a planner or settings error can never
  break the live handler (`TestExceptionSafety`).
- **No-leak by construction:** no route in the planner emits a secret/price/ETA; the
  preview redactor is a second layer; the helper has no `bot`/`session`/`message`
  parameter so it cannot send Telegram or touch the DB (`TestNoSideEffects`).

## 8. How to enable locally (do NOT enable in production yet)

```bash
# .env (local only)
SALES_DIALOGUE_MANAGER_SHADOW_ENABLED=true
```

Then run the bot in polling mode and message it. **Do not** set this in any production /
VPS environment until parity data has been reviewed.

## 9. How to inspect logs

Filter the structured logs for the event:

```bash
# dev: human-readable console
python -m apps.bot.main   # then watch stdout for sales_dialogue_shadow_decision

# prod-style JSON (e.g. via Loki / jq)
... | jq 'select(.message == "sales_dialogue_shadow_decision")'
```

Compare `sdm_next_action` (what the manager would do) against the live behaviour for the
same `user_id` / message to measure parity. Track disagreement rate per intent.

## 10. Next step after collecting parity data

1. **Add per-branch `live_route` labels** (price / catalog / measurement / operator /
   warranty / objection / stop / ai_fallback) at the live return points so the comparison
   is exact rather than `pre_route` only.
2. Review the **disagreement report**; fix the inherited detector gaps (report 144 R1/R3:
   `necha pul`, Cyrillic `гули`, robust stop) that show up.
3. Once parity is high, move to **question-only assist** (manager supplies the next
   question text for the existing ask branches) — still gated, still no autonomous send.
4. Only then consider a guarded *active* mode behind `SALES_DIALOGUE_MANAGER_ENABLED`.

---

## Test results

| Suite | Tests | Result |
|---|---:|:--|
| `test_sales_dialogue_shadow_integration.py` | **76** | ✅ |
| `tests/unit/bot` | 1,023 | ✅ |
| `tests/unit` (whole) | 7,782 (+1 skipped) | ✅ |
| `tests/simulation/agent` | 262 | ✅ |
| `ruff check .` | — | ✅ clean |
| `black --check apps/bot core shared tests docs/AI_AGENT_SYSTEM` | 605 files | ✅ clean |

**Live bot behaviour changed: NO** (flag default false; wired block is a no-op when off).
