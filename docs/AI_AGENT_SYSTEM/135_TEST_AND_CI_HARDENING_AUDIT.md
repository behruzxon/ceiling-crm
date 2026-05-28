> Status: AUDIT REPORT. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1: NOT APPLIED.
> Live sender: NOT ENABLED. Campaign send: NOT ENABLED. Operator reply live send: NOT ENABLED.

# 135 — Test and CI Hardening Audit

A brutally honest read of test quality, CI gating, mypy debt, and the cheapest fixes.

---

## 1. Headline numbers

| Layer | Files | Tests (est.) | Quality |
|---|---|---|---|
| `tests/unit/services/` | many | strongest core | Mostly mock-heavy unit tests with clear contracts. |
| `tests/unit/safety/` | small | targeted | Few but high-signal. |
| `tests/unit/docs/` | ~19 | substring | Validate text presence in doc files. |
| `tests/integration/` | 29 files | 463 | Wires real services with mocked DB sessions. |
| `tests/simulation/` | 6 files | 194 | Scenario-based agent paths; excellent. |
| `tests/e2e/` | dir exists | 0 | Empty. |
| **Total** | 256 files | ~6,795 | — |

---

## 2. Test quality, brutally honest

### Strong

- Pure-function services have direct, deterministic unit tests
  (`lead_signal_service`, `deal_probability`, `revenue_predictor_service`,
  `negotiation_engine_service`).
- Simulation lab covers 80+ scenarios end-to-end through signal → decision → offer →
  orchestrator. This is the single best safety net we have.
- Service tests use `AsyncMock`-based repo fixtures consistently; mock surface stable.
- Conftest fixtures are shared and minimal.

### Weak

- `tests/unit/docs/` is mostly `assert "string" in content`. These tests catch *documentation
  drift*, not behavior. Useful but easily confused with coverage.
- Bot **handler** tests verify the file imports — they do not exercise FSM transitions or
  callback dispatch.
- Web **template** tests assert text presence — they do not exercise the JS that runs in the
  browser.
- Integration tests mock the DB session — they do not test against a real Postgres.
- No tests assert "all migrations apply cleanly on an empty database".
- No tests assert "no two migrations share a `down_revision`".
- No tests assert the "callback prefix uniqueness" invariant the bot relies on.
- No fuzz tests against `sanitize_user_text_for_prompt`.
- No tests assert that `DEFAULT_BASE_PRICES` is not referenced by any customer-facing path.
- No tests for the runtime-settings cache TTL behavior.
- No tests for handoff SLA timer (because the timer doesn't exist yet).
- No load / stress tests; no concurrency tests on the rate limiter.

---

## 3. CI gating audit

`.github/workflows/ci.yml`:

| Job | Gating |
|---|---|
| Lint (`ruff check`) | Hard fail |
| Format (`black --check`) | Hard fail |
| Type (`mypy . --ignore-missing-imports`) | **`continue-on-error: true`** — non-blocking |
| Test (`pytest tests/unit/`) | Hard fail |
| Docker build | Hard fail |

### mypy debt

mypy is **not strict**:

- `ignore_missing_imports = true`
- `disallow_untyped_defs` not set
- `disallow_incomplete_defs` not set
- tests fully ignored (`module = "tests.*"` → `ignore_errors = true`)

mypy run today reportedly surfaces ~430 errors (per doc 121). They are not blocking. Cleanest
fix path: a multi-PR cleanup that incrementally narrows the per-module overrides until the
codebase passes `mypy --strict` on a known-clean module list. Do *not* flip `--strict` in one
shot.

### ruff debt

`pyproject.toml` ignores 25+ pre-existing-violation rules (E501, B008, F821, ANN001, etc.).
This is a deliberate trade-off — clean these up in dedicated PRs, one rule at a time.

---

## 4. Top 40 missing tests (ranked)

Pre-Stage-1:

1. Architecture lint: `apps/` does not import `infrastructure/` directly.
2. Architecture lint: `apps/bot/handlers/` does not import `DEFAULT_BASE_PRICES`.
3. Architecture lint: `apps/bot/handlers/` does not import internal admin/security services
   it shouldn't (allowlist).
4. Migration consistency: no duplicate `down_revision`.
5. Migration consistency: head is unique.
6. Migration consistency: each migration upgrade+downgrade is reversible on a sandbox DB.
7. Sanitize fuzz: 100+ random prompt-injection variations are all blocked.
8. Sanitize fuzz: 100+ random AI-reply leak variations are all blocked.
9. Output validator: every forbidden marker is rejected.
10. CSRF: missing token returns 403 on any POST.
11. RBAC: API admin routes return 403 without an admin role.
12. Web `/login`: brute force blocked after N attempts.
13. Web `/login`: constant-time comparison verified by structural test.
14. Bot smoke: `build_dispatcher()` returns successfully with no env (already exists; expand).
15. Scheduler smoke: every job module imports without side effects.
16. Settings: every dangerous flag defaults False.
17. Settings: `allow_live_flags=false` blocks runtime mutation of live flags.
18. Agent sandbox: every "block reason" is exercised by a unit test.
19. Agent queue: an expired record cannot transition to APPROVED.
20. Approved sender: an APPROVED record fails the safety re-check is marked failed, not sent.
21. Memory: phone-masking is irreversible.
22. Memory: TTL prune leaves rows ≤ 60 days intact.

Stage 1 + after:

23. Handoff dedup: two simultaneous create_handoff calls for the same lead make one row.
24. Handoff SLA: missed-SLA record auto-escalates (when feature lands).
25. Operator reply: send is denied when `crm_operator_reply_enabled=false`.
26. Campaign drafts: send is denied unconditionally today.
27. CRM mutation audit (Level 3): every mutation produces an audit row.
28. Stage 1 observation: every safety_flag value has a unit test.
29. Rate limit: per-user sliding window respects clock drift.
30. Rate limit: cross-user isolation under bursts.
31. Bot callback: each prefix has at most one handler.
32. Bot FSM: every state has a `/cancel` exit.
33. Bot text matchers: every BTN_* tap is handled before the catch-all.
34. Web `/agent`: typed modal renders the actual queued message.
35. Web `/agent`: approve/reject calls back into the queue service with the correct id.
36. Web `/crm/{id}`: notes write requires CSRF.
37. Web `/crm/{id}`: tags write requires CSRF.
38. Web `/crm`: live summary polls a fresh endpoint and respects backoff.
39. Analytics: chart payload is cacheable for 60s.
40. Missed leads: summary returns < 100ms on 10k contacts (with materialized view).

---

## 5. CI hardening suggestions

1. Add a `mypy-blocking` job that runs `mypy` against a known-clean module list
   (`apps/api/dependencies/auth.py`, `apps/web/auth.py`, `shared/utils/sanitize.py`, etc.).
   Flip to hard-fail. Grow the list one module per PR.
2. Add a `smoke-import` job that runs `python -c "import apps.{api,web,scheduler,bot}.main"`.
3. Add a `smoke-build` job that runs `from apps.bot.main import build_dispatcher;
   build_dispatcher()`.
4. Add a `db-migrate` job that runs `alembic upgrade head` against an empty Postgres in CI.
5. Add `pip-audit` (vulnerability scan).
6. Add `bandit` (security lint) as an optional non-blocking job; add findings to dashboard.
7. Add a `docs-link-check` job (broken cross-doc links).
8. Add an artifact upload for the dry-run JSON (doc 129).
9. Add a coverage threshold (start at 50% lines for `core/services/`, ratchet up).
10. Add a `runtime-cycle-detect` job using `pydeps` or similar to assert no import cycles.

---

## 6. Recommendation

- Keep lint blocking; do not loosen.
- Do **not** flip `mypy --strict` in one shot; ratchet by module.
- Add the 22 pre-Stage-1 tests in §4 before any live flag flip. They are cheap.
- Promote `tests/simulation/` from "lab" status to "must pass" — it is the highest-signal
  surface we have.
- Treat `tests/unit/docs/` as documentation drift detectors, not coverage. Keep them but rename
  the folder to `tests/unit/_docs/` to lower confusion (optional, after Stage 1).

Test score: **7.5/10**.
CI gating score: **6.5/10** (mypy non-blocking is the headline gap).
Combined hardening score: **7.0/10**.
