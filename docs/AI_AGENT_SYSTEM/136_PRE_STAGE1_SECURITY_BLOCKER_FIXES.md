> Status: SECURITY HARDENING. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1: NOT APPLIED.
> Live sender: NOT ENABLED. Campaign send: NOT ENABLED. Operator reply live send: NOT ENABLED.

# 136 — Pre-Stage 1 Security Blocker Fixes (Step 9.1)

This note records the local-only security hardening done to close two of the
four hard blockers listed in `134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md` §1.
Nothing here changes runtime behavior until the corresponding env flag is
flipped on the VPS.

---

## 1. CSRF middleware wired into the web app (Blocker §1.4)

### Status

**CLOSED locally.** The middleware is now mounted in `apps/web/main.py`. It is a
no-op until `ADMIN_CSRF_ENABLED=true`.

### What changed

| File | Change |
|---|---|
| `apps/web/csrf_middleware.py` | **New.** `AdminCSRFMiddleware` (BaseHTTPMiddleware) that gates POST/PATCH/DELETE/PUT on a valid `X-CSRF-Token` header when the flag is on. |
| `apps/web/main.py` | Added `app.add_middleware(AdminCSRFMiddleware)`. No other change. |
| `tests/unit/web/test_step_9_1_csrf_middleware_wiring.py` | **New.** 41 tests covering import surface, flag default, hash helpers, app wiring, safe-method exemption, unsafe-method enforcement, error-response shape, no-leak of token / secret / session hash, no token in logs, login GET still renders. |

### Behavior matrix

| Method | `ADMIN_CSRF_ENABLED=false` (default) | `ADMIN_CSRF_ENABLED=true` |
|---|---|---|
| GET / HEAD / OPTIONS | passthrough | passthrough (exempt) |
| POST / PATCH / DELETE / PUT on `/login` | passthrough | passthrough (exempt: login predates the session) |
| POST / PATCH / DELETE / PUT elsewhere | passthrough | **requires** valid `X-CSRF-Token` header |
| Missing token | n/a | `403 {"detail": "csrf_token_missing"}` |
| Invalid format | n/a | `403 {"detail": "csrf_token_invalid_format"}` |
| Wrong session / tampered | n/a | `403 {"detail": "csrf_token_mismatch"}` |

### How the token is validated

The middleware delegates entirely to the existing `AdminCSRFService` (no new
crypto introduced):

1. Read `X-CSRF-Token` request header (no body parsing — the downstream handler
   still owns the form body).
2. Derive `session_id_hash` by SHA-256 of the session cookie value
   (cookie name from `business.admin_session_cookie_name`). If the cookie is
   absent, the hash is empty — the token must have been issued against the
   same empty hash.
3. Call `AdminCSRFService.validate_csrf_token(token, session_id_hash, secret_key, enabled=True)`.
4. On failure, return `JSONResponse(403, {"detail": sanitize_csrf_error(error)})`.

### Safety properties verified by tests

- Default flag remains `False` (`BusinessSettings.admin_csrf_enabled.default is False`).
- When flag is off the middleware is a pure passthrough (TestClient regression).
- The response never echoes the submitted token.
- The response never echoes the session hash (sha256 hex).
- The response never echoes the app secret.
- The logger never records the submitted token at DEBUG or higher (`caplog`).
- Login GET continues to render the existing template — login flow is intact.

### Staged enablement

This implements stage **S4** in `69_SECURITY_ENABLEMENT_PLAN.md`. The plan
requires S3 (session auth) to be ON first. The `/login` POST is exempted
from CSRF because there is no session-bound token to carry before login.

---

## 2. Phone masking sweep across log / notification sites (Blocker §1.3)

### Status

**CLOSED locally** for every admin-group notification text and the two known
`log.warning` call sites that emitted a raw phone. Internal CRM storage of
raw phone is unchanged (DB column still holds the original number — masking
is applied at the display / log boundary, as required).

### What changed

| File | Change |
|---|---|
| `shared/utils/phone.py` | Added canonical `mask_phone(phone)` and `mask_phone_in_text(text)` helpers, plus `MASK_PREFIX_DIGITS`, `MASK_SUFFIX_DIGITS`, `MASK_FILL` constants. |
| `core/services/lead_notification_service.py` | Imported `mask_phone`; masked `lead.phone` / `phone` in 5 admin-group composition sites: `_new_lead_text`, `_hot_lead_text`, `notify_measurement_lead`, `notify_draft_lead`, `notify_ai_lead_collected`. |
| `apps/bot/handlers/private/ai_notifications.py` | Imported `mask_phone`; the two `log.warning` calls (`phone_capture_notify_failed`, `notify_ai_lead_collected_failed`) now emit `mask_phone(phone)` instead of the raw value. |
| `tests/unit/security/test_step_9_1_phone_log_masking.py` | **New.** 43 tests: helper API, scalar masking edge cases, in-text masking, regression on `normalize_phone` / `is_valid_uz_phone` / `extract_phone_from_text`, source-level guards that the f-strings and log calls have been switched over, regression guards on the pre-existing handoff and conversation-replay masking helpers, AI-memory `phone_masked` field still present. |

### Masking shape

`mask_phone(phone)` preserves the leading **4 chars** (typically `+998`) and
the trailing **2 digits**, with `****` filling the middle. Examples:

| Input | Output |
|---|---|
| `+998901234567` | `+998****67` |
| `901234567` | `9012****67` |
| `None` / `""` / `"   "` | `""` |
| `"12345"` (shorter than `prefix+suffix`) | `"12345"` (unchanged) |

`mask_phone_in_text(text)` runs a tolerant regex across free-form text to
catch phones in admin captions even when surrounded by other characters.
It is safe to call with `None`.

### Sites that were already safe (regression-guarded)

These were inspected and verified to still mask correctly — no behavior
change was needed beyond keeping them green:

- `core/services/agent_memory_service.py` — writes `mem.phone_masked = phone[:4] + "**…**" + phone[-2:]` (never a raw `mem.phone`).
- `core/services/crm_operator_handoff_service.py` — has its own `mask_phone(...)` for handoff preview.
- `core/services/crm_conversation_replay_service.py` — has its own `mask_phone_in_text(...)` for conversation replay events.

### Sites confirmed clean by inspection

A grep across `apps/`, `core/`, `infrastructure/`, and `shared/` for
`log.(info|warning|error|debug|exception).*phone` returned only three hits;
two of them (`ai_notifications.py:118` and `:239`) are fixed by this change.
The third — `apps/bot/handlers/private/support.py:68` `log.info("start_share_phone", user_id=user_id)` — does not log the phone itself, only an
event marker plus the user id.

The customer-facing bot may still ask the user for and confirm back the
phone — that is the intended product behavior. The mask is applied at the
**admin / log / notification boundary**, not inside the user conversation.

---

## 3. Files touched

```
apps/bot/handlers/private/ai_notifications.py     (mask log calls)
apps/web/csrf_middleware.py                       (new)
apps/web/main.py                                  (add_middleware)
core/services/lead_notification_service.py        (5 mask sites)
docs/AI_AGENT_SYSTEM/136_PRE_STAGE1_SECURITY_BLOCKER_FIXES.md  (this doc)
shared/utils/phone.py                             (mask helpers)
tests/unit/security/__init__.py                   (new package)
tests/unit/security/test_step_9_1_phone_log_masking.py   (43 tests)
tests/unit/web/test_step_9_1_csrf_middleware_wiring.py   (41 tests)
```

No migrations. No new dependencies. No env-var additions (the
`ADMIN_CSRF_ENABLED` flag already existed; this change only mounts the
middleware that reads it).

---

## 4. Flags unchanged

The full doc-114 `Stage 1 env flag matrix` is unchanged after this step:

- `ADMIN_CSRF_ENABLED=false` (still the default; flip to `true` only after
  `ADMIN_SESSION_AUTH_ENABLED=true`, per doc 69 stage S4).
- All `AGENT_*` flags untouched.
- All `CRM_*_ENABLED` send-side flags untouched.
- `LOG_ONLY` flags untouched.

---

## 5. No-send safety

This change does not touch any send path:

- No bot messages produced or scheduled.
- No Telegram API calls added.
- No OpenAI calls added.
- No Celery tasks added.
- No DB migrations.
- No new HTTP routes — only a middleware on the existing ones.

Producing a 403 from a write attempt while `ADMIN_CSRF_ENABLED=false` is
impossible (the middleware short-circuits at the first `if`).

---

## 6. Remaining blockers (from doc 134 §1)

| # | Blocker | Status |
|---|---|---|
| 1 | Real `pg_dump` / `pg_restore` drill on a copy | **OPEN** — Ops to execute against a copy, paste output into `_artifacts/`. |
| 2 | `scripts/production_deploy_dry_run_check.py` JSON artifact committed | **OPEN** — Ops to run the script with `--json` and save under `docs/AI_AGENT_SYSTEM/_artifacts/dry_run_<date>.json`. |
| 3 | Phone masking sweep | **CLOSED** by this step. |
| 4 | CSRF middleware wired | **CLOSED** by this step. |

### Final recommendation

Stage 1 readiness is now gated only on the two **operational** blockers (§1.1
and §1.2). Both are runbook executions, not code changes. Once those two
artifacts land:

1. Proceed with the doc-128 VPS bring-up sequence (API → Bot → Web → Scheduler,
   one at a time, smoke tests in between).
2. Flip `ADMIN_CSRF_ENABLED=true` **only after** `ADMIN_SESSION_AUTH_ENABLED=true`.
3. Stage 1 flag flip (decision engine + LOG_ONLY) stays unchanged from the
   doc-134 §5 sequence.

Until then: **Deploy NO. VPS NO. Flags NOT ENABLED. Stage 1 NOT APPLIED.**
