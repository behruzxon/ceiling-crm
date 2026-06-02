# 157 — Bot Knowledge Retrieval from DB (gated)

> **Status banner**
>
> - Deploy: NO · VPS: NO · Push: pending approval
> - DB / migrations: **none** (reuses `agent_knowledge_items` from doc 156)
> - Flag: `AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED` — **default FALSE** → pure no-op, bot unchanged
> - No OpenAI, **no embeddings** (pure keyword matching) · no Telegram send · no auto-reply
> - Production token: NOT USED · Real OpenAI: NOT CALLED in tests

Closes the loop opened by the Unknown Questions Inbox → Capture v2 → Knowledge
Base CRUD chain: when enabled, the bot answers matching questions from **active**
admin FAQ items *before* falling back to OpenAI.

## 1. Purpose

Let admin-authored active FAQs actually answer customers — without a code deploy —
while keeping production behaviour unchanged until the flag is explicitly enabled.

## 2. Flags (in `BusinessSettings`)

| Env var | Default | Meaning |
|---------|---------|---------|
| `AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED` | **false** | Master switch. Off → no DB lookup, behaviour identical to before. |
| `AGENT_KNOWLEDGE_DB_LOOKUP_MIN_SCORE` | `0.75` | Minimum match score to answer from KB. |
| `AGENT_KNOWLEDGE_DB_LOOKUP_LIMIT` | `5` | Max candidates scored per query. |
| `AGENT_KNOWLEDGE_DB_LOOKUP_MAX_ANSWER_CHARS` | `1200` | Answer truncation length. |

## 3. Position in the bot flow

The lookup runs **only in the AI-fallback path**, after every deterministic route
has had priority and returned:

```
stop / low-interest / pre-LLM safety  ─┐
greeting · catalog/design · objection  │  all return early (unchanged)
price · operator · measurement         │
generic confirmations · warranty FAQ   │
auto-reply · rate-limit                ─┘
        │  (still no answer → AI fallback)
        ▼
  AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED?  ── off ─▶ OpenAI fallback (unchanged)
        │ on
        ▼
  find_best_knowledge_answer(active FAQ)
        │ match ≥ min_score ─▶ reply from KB, return (NO OpenAI, NO unknown capture)
        │ no match ──────────▶ OpenAI fallback (unchanged)
        │ lookup error ──────▶ log warning, OpenAI fallback (unchanged)
```

Wired in both `handle_ai_question` and `handle_ai_message` via
`_maybe_answer_from_knowledge(message, user_id, text)` — placed right after the
rate-limit check and before the typing action / `_call_ai`. On a KB match it
replies and returns, so there is no typing reaction, no OpenAI call, and no
unknown-question capture (a KB answer is a success).

## 4. Matching algorithm (V1, pure)

`core/services/agent_knowledge_service.py`:

- `normalize_knowledge_query` — latinize Cyrillic, lowercase, strip punctuation,
  collapse whitespace.
- `is_lookupable_query` — reject empty, prompt-injection, secret-bearing, bare
  stopwords (salom/ok/rahmat/kerakmas/narx/katalog/operator/dizayn/…), and very
  short / single-token queries.
- `score_knowledge_match` (0..1): exact normalized **question** = 1.0; exact
  **alias** = 0.95; otherwise the best **token-overlap coefficient**
  `|∩| / min(|q|,|f|)` against question (×1.0), aliases (×0.9), title (×0.6).
- `search_active_knowledge_items` — only `status=active`, the given `language`
  (default uz), and retrieval categories (`faq`, `warranty`, `process`,
  `service_area`, `objection`, `other` — **price/catalog are excluded**; those are
  deterministic routes). Scores candidates, sorts by score desc then `priority`.
- `find_best_knowledge_answer` — returns the top match at/above `min_score`, else
  `None`.
- `render_knowledge_answer` — uses only the saved (already-sanitized) answer text,
  truncates to `max_chars`, appends a soft CTA (“Yana savolingiz bo'lsa, yozing 😊”).
  Never exposes tags / source / metadata.

No OpenAI, no embeddings, no network — just string normalization + token overlap.

## 5. Safety rules

- **Default OFF** — no behaviour change until the flag is set.
- **Deterministic routes always win** (price/catalog/operator/measurement/safety/
  stop are handled and returned before the lookup runs).
- **Never answers** prompt-injection / secret / system / admin-style queries
  (`is_lookupable_query` rejects them) — and the pre-LLM safety guard already
  blocked the obvious ones earlier.
- **Price/catalog excluded** from retrieval categories (no invented prices; those
  go through the calculator / catalog resolver).
- **Failure-safe** — `_maybe_answer_from_knowledge` wraps everything; a lookup
  error logs `agent_knowledge_db_lookup_failed` and returns False so the normal
  OpenAI flow continues. It never raises into the reply path.
- **No knowledge mutation** during replies; **no Telegram send** from admin/web;
  **no auto-reply** beyond the bot's existing single reply.
- Logs record `user_id` / `item_id` / `score` only — never the query text or answer.

## 6. Rollout plan

1. Merge with the flag **off** — zero production change.
2. Author a few **active** FAQs in `/agent/knowledge` (or promote from the inbox).
3. On a TEST bot, set `AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED=true`, ask a matching
   question, confirm the KB answer (and that OpenAI was not called), then revert.
4. Enable in production via the env flag once satisfied. Tune `MIN_SCORE` if needed.

## 7. Rollback plan

Set `AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED=false` (or remove it) and restart — instant
no-op, no data change. Code rollback is a plain revert of this branch. No migration
to undo.

## 8. Deferred (next)

- Vector / embedding semantic search (this V1 is keyword-only).
- Knowledge **versioning + approval workflow** (draft→review→live, rollback).
- Multi-language retrieval tuning beyond `uz`.
- **Price Settings UI** and **Catalog Link / Alias Manager** (remaining doc-152 gaps).
- Per-FAQ analytics (which items answer, hit-rate) and an admin “bot lookup ON/OFF”
  status indicator.

## 9. Tests

- `tests/unit/services/test_agent_knowledge_retrieval_service.py` — normalize,
  lookupable gate (stopwords/short/injection/secret), scoring matrix, render
  safety, async search/find_best with a fake session, priority tiebreak, no-OpenAI.
- `tests/unit/bot/test_agent_knowledge_db_lookup.py` — flag off → no lookup; on +
  match → reply + True (OpenAI skipped); no match / error → False (flow continues);
  placement after deterministic routes & before `_call_ai`; no unknown capture on
  KB answer; reaction wiring intact; no secrets in logs.
- `tests/unit/bot/test_knowledge_bot_unchanged.py` — updated: lookup is gated +
  default OFF; file-based KB still used; service stays admin-safe.

## 10. Files

- `shared/config/settings.py` — 4 `AGENT_KNOWLEDGE_DB_LOOKUP_*` flags (default OFF).
- `core/services/agent_knowledge_service.py` — retrieval functions (§4).
- `apps/bot/handlers/private/ai_support.py` — `_maybe_answer_from_knowledge` + 2 wirings.
- `apps/web/templates/agent_knowledge.html` — note: lookup default OFF + flag name.
- Tests as listed in §9; this doc + a pointer in doc 156.
