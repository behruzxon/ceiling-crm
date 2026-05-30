> Status: LOCAL FEATURE (F3 of feature/local-agent-web-polish pack).
> Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1 LOG_ONLY: NOT APPLIED.
> Live OpenAI: NOT CALLED. Live Telegram: NOT CALLED. DB writes: NONE.

# 139 — Manual Price Calculator UI in Contact Detail

## 1. Purpose

Give the operator an in-page calculator on the CRM contact-detail
page so they can produce a *taxminiy* estimate without leaving the
contact context. The calculator answers the question "what would the
ballpark be for **X** m² with **Y** design and **Z** addons" while
the operator is reading the conversation.

## 2. Data source

- **Per-m² rates:** `DESIGN_PRICES_CUSTOMER` from
  `shared/constants/pricing.py`. The internal-quote map
  `DEFAULT_BASE_PRICES` is **never** read by this calculator — only
  customer-facing prices are shown.
- **Discount tiers:** `DISCOUNT_TIERS` from the same module.
- **Addon unit prices:** `ADDON_PRICES` from the same module — only
  the keys exposed in `_ADDON_CATALOG` of
  `core/services/contact_price_calculator_service.py` are surfaced
  to the operator.
- **Design alias parsing:** delegated to
  `PriceCalculatorService.parse_design_from_text` so the calculator
  stays in sync with the existing bot calculator.

## 3. GET-only behaviour

- Inputs are read from optional query params on `GET /crm/{id}`:
  `calc_area`, `calc_design`, `calc_addons`.
- The form is `<form method="get">` and submits back to the same URL
  — the browser builds the query string for free.
- There is **no POST route** and the calculator never persists state.

Example:

```
/crm/42?calc_area=20&calc_design=gulli&calc_addons=led_strip,cornice
```

## 4. No persistence

- No DB write.
- No row inserted into `crm_price_estimate_history` (that table is
  fed by a different code path; this calculator deliberately bypasses
  it).
- No call to `PricingService.calculate_quote`.
- No call to AI / OpenAI / Telegram from the route, the service, or
  the template.

## 5. No-send safety

- No **Send** button.
- No **Save** button.
- No POST form.
- No JS that mutates server state.
- The Calculate button is a plain `type="submit"` on a GET form.

## 6. Taxminiy rule

- `is_estimate` is always `True` in the result.
- The estimate card always shows the banner
  *"TAXMINIY HISOB"*.
- The warning string is always:
  *"Bu taxminiy hisob. Yakuniy narx o'lchovdan keyin tasdiqlanadi."*
- The operator never sees a final-price guarantee.

## 7. Validation

| Condition | Behaviour |
|-----------|-----------|
| `calc_area` missing or unparseable | `is_valid=False`, friendly error "Maydonni kiriting …" |
| `calc_area < 1` | `is_valid=False`, error "Maydon juda kichik …" |
| `calc_area > 500` | `is_valid=False`, error "Maydon juda katta …" |
| `calc_design` missing | falls back to `_DEFAULT_DESIGN = "adnatonniy"` (lowest customer-facing rate) |
| `calc_design` alias | resolved via `PriceCalculatorService.parse_design_from_text` |
| `calc_addons` unknown keys | silently skipped (never produce negative price) |
| `calc_addons` duplicates | de-duplicated server-side |

## 8. Limitations

- Perimeter for per-meter addons is estimated as `4 * sqrt(area)` (the
  same heuristic `PricingService` and `revenue_predictor_service` use).
- Chandelier / spot hole counts are fixed to `1` in this UI — for
  multi-hole quotes, use the bot calculator or generate a real
  `Quote`.
- The select offers only customer-facing designs; the internal
  quote categories (`CeilingCategory.*`) are intentionally not
  exposed.

## 9. UI placement

`apps/web/templates/crm_contact_detail.html` sidebar, between the F2
*Operator AI Reply Suggestions* panel and the *AI Trace Viewer*
section. Uses existing `vp-card`, `vp-input`, `vp-select`,
`vp-btn-primary`, `vp-badge-info`, and `vp-empty-state` classes for
visual consistency.

## 10. Tests

- `tests/unit/services/test_f3_contact_price_calculator_service.py`
  — service-level invariants: input parsing, area bounds, design
  resolution + alias support, addon parsing, discount application,
  warning text, no `DEFAULT_BASE_PRICES` exposure, no negative total,
  frozen dataclasses.
- `tests/unit/web/test_f3_manual_price_calculator_ui.py` — template:
  panel present, GET-only form, taxminiy badge / warning text,
  no-send / no-Save / no-POST guarantees, no Telegram / OpenAI text,
  no DB-write JS, mobile-safe classes.

## 11. Next step

`F4 — Next Best Action panel per contact`. A new pure
`core/services/next_best_action_service.py` will compose lead state
+ score + last message into a 1-line "do this next" recommendation
that renders alongside the calculator and the suggestion panel.
