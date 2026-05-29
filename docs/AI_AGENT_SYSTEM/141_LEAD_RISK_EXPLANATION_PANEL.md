> Status: LOCAL FEATURE (F5 of feature/local-agent-web-polish pack).
> Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1 LOG_ONLY: NOT APPLIED.
> Live OpenAI: NOT CALLED. Live Telegram: NOT CALLED. DB writes: NONE.

# 141 — Lead Risk Explanation Panel

## 1. Purpose

Surface a single-page explanation of **why** a lead is currently
low / medium / high risk. The operator gets a risk badge, a numeric
score and confidence, and 3-5 short Uzbek bullet reasons composed
from the signals the CRM already has on the contact.

Pure deterministic rules; no AI; no send; no DB write.

## 2. Deterministic signals

`core/services/lead_risk_service.py :: explain_lead_risk` walks the
following signals and assigns each a weight. The cumulative score
buckets the lead into low / medium / high. Confidence rises by a
small amount with every signal that fired so a contact with only
one weak indicator stays in **`unknown`**.

| Signal | Direction | Bucket impact |
|---|---|---|
| `lead_status` in `won / resolved / deal / completed` | strong negative | hard **low** with `closed_status` reason |
| `lead_status` in `lost / stopped / closed` | strong positive | hard **high** with `closed_lost` reason |
| Stop signal in last inbound (`kerak emas`, `qiziqmayman`, …) | +40 | likely high |
| Phone empty AND lead is hot (score ≥ 60 or temp=hot) | +30 | likely high |
| Phone empty AND lead is warm | +15 | medium |
| Phone empty (generic) | +10 | small lift |
| Phone present | −15 | lowers risk |
| Price intent AND area on file missing | +15 | medium nudge |
| Area on file | −10 | lowers risk |
| District on file | −5 | small lower |
| Operator request in last inbound | +10 | small lift |
| No recent inbound | +10 | small lift |
| `next_best_action.action_key == "ask_phone"` or `priority == "now"` | +5 | tip-into-high |
| `next_best_action.action_key == "schedule_measurement"` | −10 | lowers risk |

After signal aggregation:

| Final `score` | `risk_level` | `badge_tone` |
|---|---|---|
| ≥ 70 | `high` | `danger` |
| 35–69 | `medium` | `warning` |
| < 35 | `low` | `success` |
| confidence < 20 AND only one reason | `unknown` | `neutral` |

Reasons are sorted by absolute weight and capped at **5** for a
compact panel.

## 3. No-AI / no-send safety

- **No AI call.** Rules only.
- **No DB write.**
- **No Telegram link.** The panel never includes a `t.me` URL or
  `api.telegram.org` reference.
- **No Send button.**
- **No POST form.** No `<form>` of any kind inside the panel.
- **No flag toggle handlers.**
- **No fake ETA.** Strings like *darhol / hozir / bugun* never appear
  in any rule output (word-boundary asserted by tests).

## 4. Data sources

All read-only, all from the existing `GET /crm/{id}` route context:

- `contact.lead_status`, `contact.phone`, `contact.lead_score`,
  `contact.temperature`.
- `contact.metadata.area_m2`, `contact.metadata.district`.
- `messages` (the same payload F2 / F4 already use — supports
  list-of-dicts, `{"items": [...]}` dict, or SimpleNamespace items).
- Optional `next_best_action` (F4 output) as a soft nudge only.

## 5. Redaction

Before any keyword match runs, the last inbound text passes through:

- `mask_phone_in_text` from `shared.utils.phone`.
- A frozen tuple of secret regexes: OpenAI `sk-…`, `Bearer …`,
  Telegram bot tokens (`123456:…`), `postgres://` / `redis://` URLs,
  and any literal `system prompt` / `internal rules` markers.

Reason labels and details are static Uzbek strings owned by the
service — they never include raw customer text — so even a secret
that survives the filter cannot escape into the rendered panel.

## 6. UI behaviour

`apps/web/templates/crm_contact_detail.html` sidebar — **between**
F4 *Next Best Action* (above) and F2 *Operator AI Reply
Suggestions* (below).

States:

| State | Renders |
|-------|---------|
| `lr` is None (route never called the service) | Empty placeholder |
| `lr.risk_level == "unknown"` | Empty placeholder with the dataclass `empty_reason` |
| Any other risk level | Risk badge + summary + score + confidence + 3-5 bullet reasons + safety note |

Each reason bullet is coloured by its `tone` (`danger` → red,
`warning` → amber, `success` → green, `info` → blue).

## 7. Limitations

- The "no recent inbound" rule sees only the messages loaded by the
  route (`limit=100`). Older histories appear as "no inbound".
- Score / confidence thresholds are constants in the module; tuning
  them is a follow-up.
- The panel is intentionally **read-only** — there's no "act on
  this" button. The F4 panel above already drives the next action.

## 8. Tests

- `tests/unit/services/test_f5_lead_risk_service.py` — risk bucket
  transitions, individual reason emission, redaction, no-fake-ETA,
  input flexibility (dict / SimpleNamespace), confidence/score
  clamping, frozen dataclass.
- `tests/unit/web/test_f5_lead_risk_explanation_panel.py` — panel
  presence, badge + score + confidence + reasons list rendered,
  no-send / no-POST / no-Telegram / no-OpenAI / no-token guarantees,
  panel ordering between F4 and F2.

## 9. Next step

`F6 — CRM docs index / admin help page`. A new `/help` route that
lists docs 100-141 by area with one-line summaries so operators can
find the right runbook without digging in `docs/AI_AGENT_SYSTEM/`.
