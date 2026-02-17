# CeilingCRM — Enterprise Telegram Automation Platform

## Architecture Level: 3 (Enterprise)

Production-ready Telegram CRM for stretch ceiling business.

### Stack
| Layer | Technology |
|---|---|
| Bot | aiogram 3.7 + aiogram-dialog |
| DB | PostgreSQL 15 + SQLAlchemy 2.0 async |
| Cache | Redis 7 |
| Queue | Celery 5 + Redis broker |
| Scheduler | APScheduler 3 |
| Monitoring | Sentry + Prometheus + Grafana |
| AI | OpenAI GPT-4o (guardrailed) |

### Quick Start (Development)

```bash
# 1. Clone and configure
cp .env.example .env
nano .env  # fill in BOT_TOKEN and passwords

# 2. Start infrastructure
docker compose up -d postgres redis

# 3. Create venv and install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Run DB migrations
alembic upgrade head

# 5. Seed initial data
python scripts/seed_db.py

# 6. Start the bot (polling mode)
python -m apps.bot.main
```

### Project Structure
See `ARCHITECTURE.md` (generated from architecture document) for full details.

### Development Commands
```bash
# Run tests
pytest tests/unit/

# Lint
ruff check .
mypy .

# Generate new migration
alembic revision --autogenerate -m "description"

# Start full stack
docker compose --profile monitoring up -d
```

### Environment Variables
See `.env.example` for all required configuration.
