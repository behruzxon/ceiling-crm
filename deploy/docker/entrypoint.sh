#!/bin/bash
set -e

# Run schema migrations only when enabled.
#
# Default "true" preserves the historical single-process / local-dev behavior
# (each container migrates on start). In production a dedicated one-shot
# "migrate" service sets RUN_MIGRATIONS=true while every long-running service
# (bot, scheduler, celery-worker) sets it false and waits for "migrate" to
# complete — so `alembic upgrade head` runs exactly once and never races.
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

if [ "$RUN_MIGRATIONS" = "true" ] || [ "$RUN_MIGRATIONS" = "1" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "Skipping migrations (RUN_MIGRATIONS=$RUN_MIGRATIONS)."
fi

echo "Starting application..."
exec "$@"
