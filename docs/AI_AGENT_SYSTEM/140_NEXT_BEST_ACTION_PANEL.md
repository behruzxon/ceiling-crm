> Status: LOCAL FEATURE (F4 of feature/local-agent-web-polish pack).
> Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1 LOG_ONLY: NOT APPLIED.
> Live OpenAI: NOT CALLED. Live Telegram: NOT CALLED. DB writes: NONE.

# 140 — Next Best Action Panel

## 1. Purpose

Give the operator a single, deterministic "do this next" recommendation
at the top of the CRM contact-detail sidebar. The panel never sends a
message, never POSTs, never calls AI, and never carries a fake ETA —
it just labels the most useful next step the operator can take, with
an optional anchor jump to the right in-page panel.

## 2. Deterministic rule order

`core/services/crm_next_best_action_service.py :: compute_next_best_action`
walks the rules below in order. The first match wins.

| # | Trigger | `action_key` | `priority` | CTA |
|---|---|---|---|---|
| 1 | `lead_status` in `stopped / lost / won / resolved / closed / deal / completed` | `no_action` | `none` | — |
| 2 | Last inbound contains stop signal (`kerak emas`, `qiziqmayman`, `stop`, …) | `polite_close` | `later` | — |
| 3 | `score >= 60` or `temperature == "hot"` AND `phone` empty | `ask_phone` | `now` | `#operatorReplySection` |
| 4 | Last inbound has price intent AND `metadata.area_m2` empty | `ask_area` | `now` | `#operatorReplySection` |
| 5 | Last inbound has price intent AND area on file | `calculate_price` | `today` | `#manualPriceCalculatorPanel` |
| 6 | `phone` AND (`score >= 50` or `temperature` in `{warm, hot}`) | `schedule_measurement` | `today` | `#operatorReplySection` |
| 7 | `lead_status == "operator_needed"` OR last inbound mentions operator/menejer | `operator_followup` | `now` | `#operatorReplySuggestionsPanel` |
| 8 | No inbound message in the loaded window | `wait` | `later` | — |
| 9 | Default fallback | `clarify_need` | `soon` | `#operatorReplySuggestionsPanel` |

## 3. No-AI / no-send safety

- **No AI call.** Pure rules; no model invocation.
- **No DB write.** The function returns a frozen dataclass and never
  reaches the repository layer.
- **No Telegram link.** `cta_url` is restricted to a closed whitelist
  of in-page anchors (`is_safe_cta_url` enforces it; the test suite
  pins the allowlist).
- **No send button anywhere on the panel.**
- **No POST form.** The CTA is a plain `<a href="#anchor">` — same
  page, no navigation outside the contact detail.
- **No fake ETA.** Strings like *darhol / hozir / bugun* never appear
  in any rule output.

## 4. Inputs used

| Input | Source | Read-only? |
|-------|--------|-----------|
| `contact.lead_status` | CRM API | yes |
| `contact.phone` | CRM API | yes |
| `contact.lead_score` | CRM API | yes |
| `contact.temperature` | CRM API | yes |
| `contact.metadata.area_m2` | CRM API | yes |
| `messages.items[*].direction / sender_type / text` | CRM API | yes |
| `calculator_result` (F3) | passed by route | reserved, unused today |
| `suggestion_result` (F2) | passed by route | reserved, unused today |

The last two are accepted so a future revision can read them without a
function-signature change.

## 5. Redaction

Before any keyword match runs, the last inbound text passes through:

- `mask_phone_in_text` from `shared.utils.phone`.
- A frozen tuple of secret regexes that strip OpenAI `sk-…`,
  `Bearer …`, Telegram bot tokens (`123456:…`), `postgres://` /
  `redis://` URLs, and any literal `system prompt` /
  `internal rules` markers.

`reason` and `label` are static Uzbek strings owned by the service —
they never include raw customer text — so secrets that survive the
above filter still cannot escape into the rendered panel.

## 6. UI behaviour

`apps/web/templates/crm_contact_detail.html` sidebar, **at the top**
of the right column (above the F2 *Operator AI Reply Suggestions* and
F3 *Manual Price Calculator* cards).

States:

| State | Renders |
|-------|---------|
| `nba` is None (route never called the service) | Empty placeholder |
| `action_key == "no_action"` | Label + reason + neutral badge, no CTA |
| Any other action | Label + reason + confidence + priority badge + (optional) CTA + safety note |

## 7. Limitations

- The "no recent inbound" rule only sees the messages loaded by the
  route (`limit=100`). Older histories appear as "no inbound".
- Score / temperature thresholds are constants in the module; tuning
  them is a follow-up.
- The CTA never opens an external URL — only in-page anchors. By
  design.

## 8. Tests

- `tests/unit/services/test_f4_next_best_action_service.py` — service
  contract: every rule branch, dict/SimpleNamespace inputs, redaction,
  CTA whitelist, no fake ETA, frozen dataclass.
- `tests/unit/web/test_f4_next_best_action_panel.py` — template
  invariants: panel present, priority badge, reason, confidence, CTA
  anchor only, no Send / POST / Telegram / OpenAI / token text.

## 9. Next step

`F5 — Lead Risk Explanation panel`: composes existing signals into a
3–5 bullet risk explanation (low / medium / high). Reuses the F4
redaction helpers; sits alongside F4 in the sidebar.
