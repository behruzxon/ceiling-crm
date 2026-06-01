# 155 — Unknown Questions Capture v2

> **Status banner**
>
> - Deploy: NO · VPS: NO · Push: pending approval
> - DB / migrations: **none** — reuses the existing `agent_unknown_questions`
>   table; the new reasons are existing values in the `reason` text column.
> - Flags: none added · Production token: NOT USED · Real OpenAI: NOT CALLED
> - Read-only feedback loop — no Knowledge CRUD, no FAQ promotion, no web send,
>   no customer-facing reply change. Capture is fire-and-forget and
>   exception-isolated; it can never break a bot reply.

Builds on [153_UNKNOWN_QUESTIONS_INBOX.md](153_UNKNOWN_QUESTIONS_INBOX.md). v1
captured `safety_block` and `openai_error`. v2 widens coverage to two more
**genuine, low-noise** failure/review signals.

## 1. New reasons wired

| Reason | Trigger (live handler) | Why it's a real signal |
|--------|------------------------|------------------------|
| `no_catalog_match` | In the catalog branch of both AI handlers, `resolve_catalog_link(text)` returns **`reason == "no_alias"`** (not matched, not a confirmation, not a generic catalog word). | The user asked about a design/room (e.g. "balkon", "hammom uchun shiftlar") we couldn't map to a specific catalog. Tells admins which catalogs/aliases to add. |
| `unknown_price_question` | In the terminal price branch (price intent but **no** area/design/district parsed) **and** the message is substantive (≥ 4 words). | A real price question the bot couldn't structure (e.g. "narxlaringiz juda chalkash menga tushuntiring"). Short bare asks ("narx qancha") are the normal funnel entry and are skipped. |

Both reasons already existed in the service vocabulary and the web filter, so
**no migration and no schema change** were needed. The web filter gained the one
missing option (`unknown_price_question`); `summary.top_reasons` is a DB
`group_by(reason)` so new reasons appear automatically.

## 2. How the decision is made (pure, tested)

Two pure classifiers in `core/services/unknown_question_service.py`:

```text
classify_catalog_capture(matched, needs_confirmation, reason) -> "no_catalog_match" | None
    matched OR needs_confirmation            -> None  (success / ask-to-confirm)
    reason == "no_alias"                     -> "no_catalog_match"
    reason in {generic_catalog_trigger,...}  -> None  (normal generic catalog)

classify_price_capture(text, min_words=4) -> "unknown_price_question" | None
    len(text.split()) >= min_words           -> "unknown_price_question"
    else                                     -> None  (bare funnel entry)
```

The handler calls the classifier and only then schedules a capture via the
existing `_schedule_unknown_capture(...)` helper (fire-and-forget). The customer
still receives the exact same reply (full-catalog fallback / "ask for design")
as before — capture is purely additive.

## 3. Examples

| Customer message | Outcome |
|------------------|---------|
| `gulli` / `gulli katalog` / `mramor` | matched design → **no capture** (success) |
| `katalog` / `rasm tashla` / `namuna ber` | generic catalog → **no capture** (normal) |
| `naqsh` | ambiguous → confirmation prompt → **no capture** |
| `balkon` / `hammom uchun shiftlar` / `bolalar xonasiga shift` | `no_alias` → **`no_catalog_match`** |
| `balkon uchun dizayn bormi` | contains generic word "dizayn" → generic catalog → **no capture** |
| `narx qancha` / `necha pul` | short bare ask → **no capture** (normal funnel) |
| `gulli necha pul` | design parsed → asks area (not terminal) → **no capture** |
| `20 m2 narx qancha` | area parsed → not terminal → **no capture** |
| `narxlaringiz juda chalkash menga tushuntiring iltimos` | price intent, no slots, ≥4 words → **`unknown_price_question`** |

## 4. Reasons deferred (and why)

- **`generic_reply`** — the only deterministic "generic" reply in the live flow
  is `_NEUTRAL_REPLY`, shown when the user sends a confirmation word
  ("rahmat", "ok", "zo'r"). Those are acknowledgements, not failures — capturing
  them would be noise and violates the "don't capture confirmations" rule.
- **`unknown_design`** — the catalog resolver can't distinguish "named an unknown
  design" from "named a room"; both surface as `no_alias` (captured as
  `no_catalog_match`). True design near-misses (fuzzy 0.70–0.85) are already
  handled by a confirmation prompt — good UX, not a failure. A distinct
  `unknown_design` signal needs resolver enrichment (expose the best fuzzy
  ratio) — a future change.
- **`low_confidence` / `shadow_live_mismatch`** — these depend on the Sales
  Dialogue Manager, which today runs only in shadow/log-only mode (default OFF)
  and whose decision is computed inside a fire-and-forget task, not the live
  reply path. Reading it inline could add an extra model call. These need the
  separate "persist shadow decisions to DB" sprint first.

## 5. Privacy & safety (unchanged from v1)

Phones masked, tokens/URLs/keys redacted **before** masking, ≤300-char sanitized
preview, SHA-256 dedupe hash, chat id stored only as a hash. Capture is
fire-and-forget and wrapped so a failure only logs a warning. No reply text,
routing, or existing-capture behavior changed.

## 6. Tests

- `tests/unit/services/test_unknown_question_service.py` — +40 (classifier
  matrix, v2 reasons through build/record/severity, non-failure skips,
  sanitization re-checks).
- `tests/unit/bot/test_unknown_question_capture_v2.py` — ~60 (real resolver +
  classifier integration for catalog/price, never-capture flows, source-pin
  wiring, deferred-reasons-not-wired pins, purity).
- `tests/unit/bot/test_unknown_question_capture.py` — updated capture-site count
  (3 → 7).
- web/api filter tests extended (new option + dynamic top_reasons + no
  send/FAQ buttons).

## 7. Next sprint (unchanged)

**Knowledge Base CRUD + promote-unknown-question → FAQ** — the inbox now surfaces
catalog and price gaps too, making that sprint even more targeted. After that:
DB-level 24h dedupe, then persist SDM shadow decisions to unlock `low_confidence`
/ `shadow_live_mismatch` + a live-vs-SDM parity view.

## 8. Files

- `core/services/unknown_question_service.py` — `classify_catalog_capture`,
  `classify_price_capture`.
- `apps/bot/handlers/private/ai_support.py` — catalog + price capture wiring in
  both AI handlers (via the existing fire-and-forget scheduler).
- `apps/web/templates/agent_unknown_questions.html` — `unknown_price_question`
  filter option.
- Tests as listed in §6; this doc + a pointer added to doc 153.
