# Pre-Tool-Use Checklist

Before executing any tool, check these rules based on what you are about to do.

## Before Reading .env

- NEVER print or output the contents of `.env` files
- Only check the structure (which keys exist, not their values)
- If you need to verify a setting, check `shared/config/settings.py` for the Pydantic Settings field definition instead

## Before Editing Production Config

- Warn about the impact on running services
- List which services will be affected
- Confirm the change is intentional (not a side effect of another change)
- Files to watch: `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example`, `alembic.ini`

## Before Large Refactor

- Create a written plan first: which files change, what breaks, what the rollback is
- Get explicit approval before proceeding
- Never refactor more than 5 files in one step
- Write tests for the current behavior BEFORE changing it

## Before Editing Handlers

- Read `apps/bot/main.py` and check router registration order
- Critical order rules:
  - `order_router` BEFORE `lead_capture_router` in private_router
  - `ai_support_router` BEFORE `support_router` (catch-all last) in private_router
  - `kanban_callbacks_router` BEFORE `pipeline_callbacks_router` in callbacks_router
  - `lead_status_router` BETWEEN `kanban_callbacks_router` and `cta_callbacks_router`
- Verify your new handler does not shadow existing callback patterns

## Before Editing FSM States

- Check that every state has a handler
- Verify back/cancel buttons exist for every state
- Confirm `await state.clear()` is called at flow completion
- Check that the `StatesGroup` is imported and used in the correct handler file

## Before Editing Redis Keys

- Read `infrastructure/cache/keys.py` to check for key conflicts
- Verify TTL values are appropriate
- Use `CacheKeys` class methods to build keys (never raw strings)
- Add new TTL constants to `CacheTTL` class

## Before Editing Migrations

- Run `alembic heads` to check there is exactly one head
- NEVER modify an existing migration that has been applied
- Always create a new migration with `alembic revision --autogenerate -m "description"`
- If adding an enum value, use `ALTER TYPE ... ADD VALUE` (not a new type)
- Remember `values_callable` for any new `sa.Enum` column

## Before Editing system_prompt.py

- Cross-reference prices with `shared/constants/pricing.py` and `core/services/pricing_service.py`
- Verify any claims about products match `shared/knowledge/uz.md`
- Check that prompt injection guards are not removed
- Verify the AI persona (Madina) guidelines are preserved

## Before Deleting Files

- Search for all imports of the file: `ruff check` or grep for the module name
- Check if the file is referenced in `apps/bot/main.py` (router registration)
- Check if it is referenced in `infrastructure/di.py` (DI wiring)
- Check if it is referenced in `infrastructure/queue/app.py` (Celery task registration)
- Check if it is referenced in test files

## Before Adding Dependencies

- Check `requirements.txt` for version conflicts
- Verify the dependency is actively maintained
- Prefer stdlib or existing dependencies over new ones
- Pin to a compatible version range (e.g., `>=1.0,<2.0`)
