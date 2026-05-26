# Next Steps

This document describes the exact next development step after documentation is complete.

---

## Current State

- Phase 0 (Documentation) is complete
- The Telegram bot is production-ready and functioning
- No REST API exists
- No web dashboard exists
- Architecture is clean enough for incremental API addition

## Recommended First Implementation: Phase 1 — Foundation Cleanup

Before adding the API, fix three architectural violations that would leak into the API layer.

### Task 1: Consolidate Pricing Constants

**Why:** Design prices and addon prices are defined in 3 different files. Any price change requires updating all 3, creating inconsistency risk.

**Files to create:**
```
shared/constants/pricing.py    (new — single source of truth)
```

**Files to modify (import paths only):**
```
core/services/pricing_service.py           (import from shared/constants/pricing)
shared/utils/deal_probability.py           (import from shared/constants/pricing)
core/services/revenue_predictor_service.py (import from shared/constants/pricing)
```

**Content of `shared/constants/pricing.py`:**
- `DEFAULT_BASE_PRICES: dict[CeilingCategory, Decimal]` — from `pricing_service.py` lines 17-28 (internal quote prices: 100k-300k range)
- `ADDON_PRICES: dict[str, Decimal]` — from `pricing_service.py` lines 31-38 (currently duplicated identically in `revenue_predictor_service.py`)
- `DESIGN_PRICES_CUSTOMER: dict[str, int]` — from `deal_probability.py` lines 43-55 (customer-facing/AI display prices: 80k-140k range, string design names)
- `DEFAULT_PRICE_PER_M2: int` — from `deal_probability.py` line 56 (100,000 — fallback when design unknown)
- `DISCOUNT_TIERS: list[tuple[int, float]]` — `[(20, 0.05), (40, 0.10)]`

**Important:** `DEFAULT_BASE_PRICES` and `DESIGN_PRICES_CUSTOMER` are intentionally different price sets:
- `DEFAULT_BASE_PRICES` = actual per-category quote calculation prices (used by `PricingService` for real quotes)
- `DESIGN_PRICES_CUSTOMER` = simplified customer-facing prices (used by AI for conversational estimates and revenue prediction)

Do NOT merge them. They serve different business purposes.

**Do NOT touch:**
- Any handler logic
- Any service logic beyond import paths
- Any test logic
- Price values themselves — only move them

**Verify:**
```bash
pytest tests/unit/ -q
ruff check shared/constants/pricing.py
```

---

### Task 2: Extract Sanitization Helpers

**Why:** `core/services/ai_sales_advice.py` and `core/services/deal_closer_service.py` import `sanitize_*` functions from `apps/bot/ai/system_prompt.py` via lazy (function-level) imports. While not module-level, this still violates the dependency direction (`core` must never import from `apps`) and blocks clean API extraction.

**Files to create:**
```
shared/utils/sanitize.py    (new — pure functions, no deps)
```

**Files to modify:**
```
apps/bot/ai/system_prompt.py              (move functions out, add re-exports)
core/services/ai_sales_advice.py          (change import to shared/utils/sanitize)
core/services/deal_closer_service.py      (change import to shared/utils/sanitize)
```

**Functions to move:**
- `detect_prompt_injection(text: str) -> bool`
- `sanitize_ai_reply(reply: str) -> str | None`
- `sanitize_user_text_for_prompt(text: str, max_length: int, placeholder: str) -> str`

**Backward compatibility:** `apps/bot/ai/system_prompt.py` should re-export:
```python
from shared.utils.sanitize import (
    detect_prompt_injection,
    sanitize_ai_reply,
    sanitize_user_text_for_prompt,
)
```

This ensures any other imports from `system_prompt.py` continue working.

**Verify:**
```bash
pytest tests/unit/ -q
ruff check shared/utils/sanitize.py
python -c "from core.services.ai_sales_advice import *"  # no ImportError
python -c "from apps.bot.ai.system_prompt import sanitize_ai_reply"  # backward compat
```

---

### Task 3: Move OpenAI Client to Infrastructure

**Why:** `core/services/ai_sales_advice.py` imports `_get_client` and `_record_usage` from `apps/bot/handlers/private/ai_openai.py`. Same dependency direction violation.

**Files to create:**
```
infrastructure/ai/__init__.py        (new — empty)
infrastructure/ai/openai_client.py   (new — client singleton + usage recording)
```

**Files to modify:**
```
apps/bot/handlers/private/ai_openai.py  (move _get_client, _record_usage out; add re-exports)
core/services/ai_sales_advice.py        (change import to infrastructure/ai/openai_client)
```

**Backward compatibility:** `ai_openai.py` re-exports the moved functions.

**Verify:**
```bash
pytest tests/unit/ -q
python -c "from infrastructure.ai.openai_client import get_openai_client"
```

---

## Files NOT to Touch in Phase 1

These files must remain untouched:

- `apps/bot/main.py` — dispatcher setup
- `apps/bot/middlewares/*` — all middlewares
- `apps/bot/handlers/private/ai_support.py` — AI message handler
- `apps/bot/handlers/admin/*` — all admin handlers
- `apps/bot/handlers/callbacks/*` — all callback handlers
- `apps/bot/handlers/group/*` — all group handlers
- `apps/bot/states/*` — all FSM states
- `apps/bot/keyboards/*` — all keyboards
- `infrastructure/database/models/*` — all ORM models
- `infrastructure/database/repositories/*` — all repositories
- `infrastructure/database/migrations/*` — all migrations
- `infrastructure/di.py` — DI wiring
- `docker-compose.yml` — Docker setup
- `docker-compose.prod.yml` — production Docker

---

## After Phase 1: Phase 2 Preview

Once the 3 cleanup tasks are complete, the next step is creating the FastAPI skeleton:

```
apps/api/__init__.py
apps/api/main.py         (FastAPI app + /health)
apps/api/deps.py         (get_db dependency)
core/auth/__init__.py
core/auth/jwt.py         (token service)
```

This is entirely additive — no existing files change.

See `docs/WEB_INTEGRATION_PLAN.md` Phase 2 for full details.

---

## Test Commands

```bash
# Run all unit tests
pytest tests/unit/ -q

# Run a specific test file
pytest tests/unit/test_foo.py -q

# Lint check
ruff check .

# Type check
mypy .

# Verify imports (quick smoke test)
python -c "from shared.constants.pricing import DEFAULT_BASE_PRICES, ADDON_PRICES"
python -c "from shared.utils.sanitize import detect_prompt_injection"
python -c "from infrastructure.ai.openai_client import get_openai_client"
```

---

## Rollback Notes

Phase 1 changes are purely import-path refactors with backward-compatible re-exports. To rollback:

1. `git revert <commit>` — single commit per task recommended
2. No database migrations involved
3. No Docker changes involved
4. No config/env changes involved

If a re-export breaks due to circular import, the original function location still works — just revert the import change in the affected `core/services/` file.
