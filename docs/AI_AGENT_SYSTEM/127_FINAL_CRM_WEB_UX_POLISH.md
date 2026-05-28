# 127 — Final CRM/Web UX Polish (Step 12)

Internal UI polish pass on the CRM/Web surfaces added in Fresh Start
Steps 1–11. No production code outside of templates and one new
web route; no bot, pricing, or catalog changes.

## Pages touched

| Template | Polish |
|----------|--------|
| `apps/web/templates/base.html` | (unchanged) sidebar / topbar reviewed and confirmed consistent |
| `apps/web/templates/crm_handoffs.html` | Empty-state copy aligned to spec ("Hozir navbatda handoff yo'q"); digest card now links to standalone `/crm/operator-digest` |
| `apps/web/templates/crm_missed_leads.html` | Empty-state copy aligned to spec ("Missed leadlar yo'q — hammasi nazoratda") |
| `apps/web/templates/analytics.html` | Charts loading state + error state added; existing empty states preserved |
| `apps/web/templates/crm_contact_detail.html` | AI Trace / Conversation Replay / Price Estimate empty states tightened |
| `apps/web/templates/crm_operator_digest.html` | NEW — standalone Daily Operator Digest page |

## New route

`GET /crm/operator-digest` — registered in `apps/web/main.py`. Renders
the new `crm_operator_digest.html` shell, which fetches data from the
existing `/api/v1/admin/crm/operator-digest/daily` and `/preview`
endpoints on load. No backend changes, no new API endpoints.

The standalone view includes:
- Severity badge (green / yellow / red).
- 6-KPI grid (Open, Telefon kutadi, Tayinlangan, Urgent, High, Bugun expired).
- Metrics grid (12 detailed metric rows from the digest service).
- Top recommendations as an ordered list.
- Raw text preview block, fed by the `/preview` endpoint.
- Refresh button.
- "Yuborish (disabled)" button — clearly disabled, no active send.

The `/crm/handoffs` digest card gains a "To'liq ko'rish" link that
opens the standalone page.

## UI polish summary

- **Empty states**: standardized across handoffs / missed leads / AI
  trace / price estimates / conversation replay. Each state uses
  short Uzbek copy that is operator-friendly and doesn't promise
  anything to the customer.
- **Badges**: existing `vp-badge-*` classes left as the canonical
  system (success / warning / danger / info / neutral / hot). No new
  badge classes introduced.
- **Buttons**: `vp-btn-primary` reserved for main actions,
  `vp-btn-secondary` / `vp-btn-ghost` for safe actions, `vp-btn-danger`
  only for destructive operations. The single send-like button on
  the digest card is intentionally `disabled` and labelled
  "(disabled)".
- **Mobile**: every page uses `flex-wrap` + the existing
  `max-width: 767px` and `max-width: 1023px` media queries — no
  horizontal overflow introduced by Step 12.
- **No raw JSON dumps**: no template uses `|tojson` or otherwise
  prints raw API/metadata blobs.

## Safety constraints

- Deploy: NO.
- VPS: NO.
- Flags: NOT ENABLED.
- Stage 1 LOG_ONLY: NOT APPLIED.
- No real Telegram / OpenAI calls.
- No production migrations.
- No bot / pricing / catalog changes.
- Pure template + one new GET route (read-only shell that fetches
  existing API).

## No-send status

- No active send button exists on any CRM/Web page polished in Step 12.
- The only `Yuborish`-labelled button (digest card + standalone page)
  is rendered with the HTML `disabled` attribute AND the literal
  "(disabled)" suffix.
- No template references `/operator-digest/send` or any similar send
  endpoint. The standalone page only calls `/daily` and `/preview`.
- The operator-reply textarea on `crm_contact_detail.html` is governed
  by the existing `CRM_OPERATOR_REPLY_ENABLED` flag (default OFF).
- Sanitization for the text preview lives in the digest service and
  scrubs tokens and contiguous phone-like digit runs before any
  rendering.

## Mobile / responsive notes

- `base.html`: sidebar collapses below `1023px`; overlay closes on tap.
- `crm_handoffs.html`: KPI grid is `auto-fill minmax(160px, 1fr)`;
  digest grid uses `flex-wrap`; action buttons wrap; columns 6/7 of
  the queue table hide under `767px`.
- `crm_missed_leads.html`: filters wrap; columns 4/5 hide under
  `767px`.
- `analytics.html`: KPI grid collapses to 1 column under `479px`;
  two-column rows collapse to one under `767px`.
- `crm_contact_detail.html`: `contact-grid` is two-column on
  ≥1280px and stacks on smaller; sidebar cards have generous
  spacing.
- `crm_operator_digest.html`: digest items use `flex: 1 1 160px`
  with `flex-wrap`; under 767px each item takes the full row.

## Remaining UX debt

These are intentionally deferred — none block Stage 1 readiness:

1. **Real digest delivery channel** — currently delivery is a
   defensive no-op even when the flag is enabled. When an
   operator-DM channel is wired this should become a real send
   path behind `CRM_OPERATOR_DIGEST_DELIVERY_ENABLED`.
2. **Missed-leads data source** — the missed-leads API still returns
   an empty list. When the data source is wired the digest will
   automatically pick it up.
3. **Severity threshold tuning** — first 24-48h of Stage 1 LOG_ONLY
   observation will likely surface new thresholds; current values
   are conservative.
4. **Per-operator filter on `/crm/operator-digest`** — would be
   useful for team leads. Today's view aggregates across all
   operators.
5. **Localization** — the new copy is Uzbek-only. Ru/En variants
   should be added when the bot ru/en flows are reintroduced.

## Tests

| Suite | File | Tests |
|-------|------|-------|
| Web polish | `tests/unit/web/test_step_12_final_crm_web_ux_polish.py` | 65 |
| Standalone route | `tests/unit/web/test_step_12_operator_digest_route.py` | 33 |
| Docs | `tests/unit/docs/test_step_12_final_crm_web_ux_polish_docs.py` | 26 |
| **Total new** | | **124** |

Regression sweep also confirms the full unit + integration suite
remains green.

## Next step

- **Stage 1 LOG_ONLY apply on the VPS** (preferred when pg_dump +
  alembic upgrade + systemd + Sentry are confirmed).
- Alternatively, **Step 13 — Production Deployment Runbook & Dry
  Local Deploy Check** to script the apply process and validate it
  locally before any VPS contact.
