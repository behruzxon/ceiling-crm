> Status: LOCAL FEATURE (F2 of feature/local-agent-web-polish pack).
> Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1 LOG_ONLY: NOT APPLIED.
> Live OpenAI: NOT CALLED. Live Telegram: NOT CALLED. Sends: NONE.

# 138 — Operator AI Reply Suggestion Panel

## 1. Purpose

Help operators draft a reply faster by previewing 2–3 short Uzbek
suggestions for the **last inbound customer message** on the CRM
contact-detail page.

The panel is **suggest-only**: it never sends a message, never POSTs,
never calls Telegram or OpenAI from the browser, and never auto-fills
the operator reply box. The operator clicks **Copy**, pastes into
their reply field, edits as needed, and sends manually through the
existing operator-reply flow.

## 2. Safety guarantees

- **Default OFF.** Controlled by `OPERATOR_REPLY_SUGGESTIONS_ENABLED`
  in `shared/config/settings.py`, default `False`.
- **No send button anywhere on the panel.** The only action is a copy
  button that writes to `navigator.clipboard` and nothing else.
- **No POST.** The panel is rendered server-side from the existing
  `GET /crm/{contact_id}` route.
- **No live OpenAI call by default.** The service's default responder
  is a fully deterministic stub (`_deterministic_stub`). A custom
  `ai_responder` can be injected, but the production wiring for that
  intentionally does not exist in this PR — adding it is its own
  future change that must come with its own review.
- **No live Telegram call.** This service touches no Telegram client
  and the template renders no Telegram URLs.

## 3. Data source

- `contact` — dict from `/api/v1/admin/crm/contacts/{id}` (already fetched
  by the route).
- `messages` — `(messages or {}).get("items", [])` from the same route.

The service only reads the **last** message whose `direction ==
"inbound"` or whose `sender_type` is `user` / `customer` / `client`.
Bot and operator messages are ignored.

## 4. Redaction

Both the source-message preview **and** every suggestion text go through
`_sanitize_text`, which:

- Masks phone numbers via `shared.utils.phone.mask_phone_in_text`.
- Strips OpenAI `sk-…` tokens, `Bearer …` headers, Telegram bot tokens
  (`123456:…`), `postgres://` / `redis://` URLs, and any literal
  `system prompt` / `internal rules` markers.
- Collapses CR/LF.
- Truncates to 140 chars (preview) / 280 chars (each suggestion).

Suggestion text additionally has the words **darhol / hozir / bugun**
replaced with **tez orada** — those are operator promises only a human
should make.

## 5. UI behaviour

Located in `apps/web/templates/crm_contact_detail.html`, sidebar (right
column), between *Price Estimate History* and *AI Trace Viewer*.

States:

| State | What renders |
|-------|--------------|
| Feature disabled | Empty placeholder: "AI reply suggestions hozir o'chiq. Operator javobni qo'lda yozadi." |
| Enabled, no inbound message | Empty placeholder: "Mijozdan kelgan xabar yo'q — taklif yaratish uchun yetarli kontekst yo'q." |
| Enabled, media-only last message | Empty placeholder: "Oxirgi xabarda matn yo'q (media / sticker)." |
| Enabled with text | Source preview card + 2–3 suggestion cards + safety note |

Each suggestion card shows a **tone badge** (professional / friendly /
clarification / closing), a **risk badge** (low / medium / high), the
suggestion text, the reason, and a **Copy** button.

Below the list: a safety note —
*"Bu yordamchi takliflar. Operator har doim tahrirlab yuborishi shart."*

## 6. Intent detection

The deterministic stub chooses one of five intents from the source
text — `price`, `stop`, `greeting`, `clarification`, `generic` — and
returns 3 canned suggestions tailored to that intent. **Price intent
always includes the word "taxminiy"** so the operator never makes a
firm price promise.

## 7. Limitations

- Suggestions are deterministic and product-area-aware but **not
  conversational** — they don't remember earlier messages.
- The custom `ai_responder` injection point is not wired in production
  by this PR — only tests use it via mocks. Adding a production
  responder is a separate, gated feature.
- The Copy button uses `navigator.clipboard.writeText` — falls back
  silently if the browser does not support it (no JS error, no
  paste).

## 8. Tests

- `tests/unit/services/test_f2_operator_reply_suggestion_service.py`
  — 40+ tests covering the service contract, feature-flag gating,
  intent detection, redaction, forbidden-promise stripping, and
  injection of a mock responder.
- `tests/unit/web/test_f2_operator_reply_suggestion_panel.py` — 25+
  tests covering the panel HTML: title, disabled state, copy button,
  no-send guarantees, no token/session-hash text in the new markup,
  feature flag default.

All tests run without DB / Redis / network access — pure unit tests.

## 9. Next step

`F3 — Manual Price Calculator UI in contact detail`: reuse
`PricingService.estimate` to show an inline calculator beneath the
suggestion panel. Read-only; no persistence.
