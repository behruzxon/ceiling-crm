# 126 — Operator Notification Digest / Daily Queue Summary (Step 11)

## Purpose

Internal daily CRM-health summary for admins/operators: how many
handoffs are open, how many are urgent, how many were resolved or
expired today, what missed leads need attention, and prioritized
recommendations. **Internal only — no user-facing sends.**

## Digest fields

### Handoff summary
- `total_open` — handoff rows with `status=open`
- `waiting_phone` — `status=waiting_phone`
- `assigned` — `status=assigned`
- `contacted_today` — `status=contacted`, contacted/updated within 24h
- `resolved_today` — `status=resolved`, resolved within 24h
- `expired_today` — `status=expired`, updated within 24h
- `urgent_open` / `high_open` — active rows by priority
- `oldest_wait_minutes` — longest active-row age

### Missed-lead summary
- `total_missed`
- `critical_missed`
- `high_missed`
- `hot_unanswered`
- `operator_waiting`
- `phone_shared_no_followup`

### Workload
Per-operator: `assigned_open`, `urgent_assigned`, `oldest_assigned_minutes`.

### Severity (green / yellow / red)
- **green**: nothing urgent, no critical missed lead, oldest wait <2h
- **yellow**: high-priority handoff exists, or 1 urgent, or oldest ≥2h
- **red**: any critical missed lead, OR ≥3 urgent open, OR urgent open
  with oldest wait ≥60 min

### Recommendations
Prioritized list of operator instructions. Internal hints, not user
messages:
- "Critical missed leadlarga javob bering"
- "Avval urgent handofflarni ko'ring"
- "Telefon qoldirgan mijozlarga aloqani tekshiring"
- "Expired bo'lgan handofflarni review qiling"
- "High priority handofflarni navbat bo'yicha oling"
- "Hot leadlarga javob qaytaring"
- (quiet state) "Navbat tinch. Yangi handofflar uchun kuzatuvni davom ettiring."

## API endpoints

`apps/api/routes/admin_crm_operator_digest.py`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/admin/crm/operator-digest/daily` | Structured digest JSON |
| GET | `/api/v1/admin/crm/operator-digest/preview` | Sanitized text preview |

Both require `require_api_token` (same Bearer guard as the rest of
`/api/v1/admin/*`). Both accept `hours` (1..168, default 24).

## Web UI

`/crm/handoffs` page gains a **Daily Operator Digest** card above the
Operator Workload card:
- Severity badge (green / yellow / red).
- Compact grid of 9 key metrics with color-coded left borders.
- Top-3 prioritized recommendations.
- "Yangilash" refresh button.
- "Yuborish (disabled)" send button that is **disabled** and labelled
  as such. Send is intentionally not wired.

## Scheduler / delivery status

- New job `crm_operator_digest_daily` registered in
  `apps/scheduler/main.py`, cron at the configured hour (default 09:00).
- Job is fully gated:
  - When `CRM_OPERATOR_DIGEST_ENABLED=false` (default) → no-op,
    no DB session opened.
  - When enabled but `CRM_OPERATOR_DIGEST_DELIVERY_ENABLED=false`
    (default) → builds digest, logs summary, no external send.
  - When delivery enabled → currently still a defensive no-op; no
    channel is wired and the job module does not import aiogram.

## Default-OFF safety

| Flag | Default | Effect when off |
|------|---------|-----------------|
| `CRM_OPERATOR_DIGEST_ENABLED` | `false` | Job no-ops entirely |
| `CRM_OPERATOR_DIGEST_DELIVERY_ENABLED` | `false` | Even if job runs, no send |
| `CRM_OPERATOR_DIGEST_HOUR` | `9` | Cron hour (0..23) |

The API endpoints + web card work without these flags — they are
purely additive observability surfaces.

## No-send guarantee

- `core/services/crm_operator_digest_service.py`: no `aiogram` /
  `openai` imports. Verified by tests.
- `apps/api/routes/admin_crm_operator_digest.py`: no `aiogram` /
  `openai` imports. No `send_message`, no `.delete(`.
- `apps/scheduler/jobs/crm_operator_digest_jobs.py`: no aiogram/openai
  imports. Verified by tests (`test_no_aiogram_import`,
  `test_no_openai_import`, `test_no_send_message`).
- Web template: send button rendered with the `disabled` attribute
  and the literal "(disabled)" label.
- `sanitize_preview` scrubs tokens (`sk-…`, `Bearer …`) and contiguous
  phone-like digit runs (≥7 digits) before any preview text is
  returned. Final pass also runs on the full rendered digest.

## Tests

| Suite | File | Tests |
|-------|------|-------|
| Service | `tests/unit/services/test_step_11_operator_digest_service.py` | 73 |
| API | `tests/unit/api/test_step_11_operator_digest_api.py` | 36 |
| Web UI | `tests/unit/web/test_step_11_operator_digest_web.py` | 39 |
| Scheduler | `tests/unit/scheduler/test_step_11_operator_digest_job.py` | 24 |
| Integration | `tests/integration/agent/test_step_11_operator_digest_flow.py` | 20 |
| **Total** | | **192** |

All 192 new tests pass. Steps 8/9 regression confirmed.

## Limitations

- Missed-lead input is currently empty by default — the missed-leads
  service exposes a list shape but no live data source feeds the API.
  Real missed-lead lists will be wired when that service is connected
  to its data source; the digest already supports them.
- Workload top-N is capped at 5 in the text renderer to keep messages
  short.
- No delivery channel is wired even when delivery is enabled; the
  delivery branch is a defensive log-only no-op.
- Severity thresholds are coarse and may be re-tuned based on
  operator feedback during Stage 1.

## Next step

- **Step 12 — Final CRM/Web UX polish** (recommended if Stage 1 still
  deferred), OR
- **Stage 1 LOG_ONLY apply** once the VPS preconditions in
  `125_STAGE_1_READINESS_REVIEW_AFTER_FRESH_START.md` are met.
