# Production Deployment Checklist

## Pre-Deploy

- [ ] All CI checks pass (lint + unit tests + migration chain)
- [ ] No secrets in committed code (security scan green)
- [ ] `.env` on server has all required variables (compare with `.env.example`)
- [ ] Database backup taken before migration
- [ ] Migration chain has single head (`alembic heads` returns 1)

## Deploy Steps

1. **Pull latest code** on the server
   ```bash
   cd /opt/ceiling-crm && git pull origin main
   ```

2. **Review pending migrations**
   ```bash
   docker compose exec bot alembic history --verbose -r current:head
   ```

3. **Take DB backup** (if migrations pending)
   ```bash
   docker compose exec postgres pg_dump -U ceiling_crm ceiling_crm > backup_$(date +%Y%m%d_%H%M).sql
   ```

4. **Pull & restart services**
   ```bash
   docker compose pull
   docker compose up -d --no-deps bot worker scheduler
   ```
   The entrypoint runs `alembic upgrade head` automatically.

5. **Verify health**
   ```bash
   docker compose ps                        # all services "Up (healthy)"
   docker compose logs --tail=50 bot        # no startup errors
   docker compose logs --tail=20 worker     # Celery connected
   docker compose logs --tail=20 scheduler  # jobs scheduled
   ```

6. **Smoke test**
   - Send `/start` to the bot in Telegram
   - Check admin group receives test notification
   - Verify Prometheus metrics at `:18080/metrics`

## Post-Deploy

- [ ] Monitor Sentry for new errors (15 min window)
- [ ] Check Grafana dashboards for anomalies
- [ ] Verify Redis connectivity (`docker compose exec redis redis-cli ping`)
- [ ] Confirm payment webhooks reachable (if Click/Payme configured)

## Rollback

```bash
# 1. Revert to previous image
docker compose up -d --no-deps bot worker scheduler  # with previous tag

# 2. If migration needs rollback
docker compose exec bot alembic downgrade -1

# 3. Restore DB from backup (nuclear option)
docker compose exec -T postgres psql -U ceiling_crm ceiling_crm < backup_YYYYMMDD_HHMM.sql
```

## Required Secrets (GitHub Actions)

| Secret | Where | Purpose |
|--------|-------|---------|
| `DEPLOY_HOST` | Repo settings | Server IP/hostname |
| `DEPLOY_USER` | Repo settings | SSH username |
| `DEPLOY_SSH_KEY` | Repo settings | SSH private key |
| `DEPLOY_PATH` | Repo settings | App directory on server |

> `GITHUB_TOKEN` is provided automatically for GHCR access.

## Environment Variables (Server .env)

See `.env.example` for the full list. Critical ones:

| Variable | Required | Notes |
|----------|----------|-------|
| `BOT_TOKEN` | Yes | From @BotFather |
| `POSTGRES_PASSWORD` | Yes | Strong random password |
| `REDIS_PASSWORD` | Yes | For production Redis auth |
| `APP_SECRET_KEY` | Yes | Random 32+ char string |
| `OPENAI_API_KEY` | Yes | For AI support features |
| `SENTRY_DSN` | Recommended | Error tracking |
| `CLICK_SECRET_KEY` | If using Click.uz | Payment webhook signing |
| `PAYME_MERCHANT_KEY` | If using Payme.uz | Payment webhook auth |
