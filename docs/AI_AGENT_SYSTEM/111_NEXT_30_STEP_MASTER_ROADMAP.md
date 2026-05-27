# Next 30-Step Master Roadmap

**Date**: 2026-05-27

## P0 — Must Before Stage 1 LOG_ONLY

| # | Step | Risk | Impact | Migration? | Deploy? |
|---|------|------|--------|-----------|---------|
| 1 | Enable ADMIN_SESSION_AUTH in production .env | LOW | HIGH | No | Yes |
| 2 | Enable ADMIN_CSRF in production .env | LOW | HIGH | No | Yes |
| 3 | Create DB backup script/procedure | LOW | CRITICAL | No | No |
| 4 | Run alembic upgrade head on VPS | MEDIUM | HIGH | Yes | Yes |
| 5 | Verify .env has all required vars on VPS | LOW | HIGH | No | Yes |
| 6 | Resolve git branch strategy (merge or keep separate) | LOW | MEDIUM | No | No |

## P1 — Strongly Recommended Before Stage 1

| # | Step | Risk | Impact | Migration? | Deploy? |
|---|------|------|--------|-----------|---------|
| 7 | Fix CI mypy or add --ignore-errors | LOW | MEDIUM | No | No |
| 8 | Re-enable F821 ruff rule, fix real undefined names | LOW | MEDIUM | No | No |
| 9 | Add TLS/nginx reverse proxy config | LOW | HIGH | No | Yes |
| 10 | Wire operator handoff into operator.py handler fully | LOW | MEDIUM | No | No |
| 11 | Connect order flow to price calculator | LOW | MEDIUM | No | No |

## P2 — During Stage 1 Observation

| # | Step | Risk | Impact | Migration? | Deploy? |
|---|------|------|--------|-----------|---------|
| 12 | Add /health endpoint for monitoring | LOW | MEDIUM | No | Yes |
| 13 | Add web handoff queue page | LOW | HIGH | No | Yes |
| 14 | Add operator queue API endpoints | LOW | MEDIUM | No | Yes |
| 15 | Add handoff auto-expire scheduler job | LOW | MEDIUM | No | Yes |
| 16 | Add e2e bot flow simulation tests | LOW | HIGH | No | No |
| 17 | Analyze real user traffic patterns | LOW | HIGH | No | No |
| 18 | Add async handler behavior tests | LOW | MEDIUM | No | No |

## P3 — Before Stage 2 DRY_RUN

| # | Step | Risk | Impact | Migration? | Deploy? |
|---|------|------|--------|-----------|---------|
| 19 | Add analytics charts to web | LOW | MEDIUM | No | Yes |
| 20 | Campaign send DRY_RUN testing | MEDIUM | HIGH | No | No |
| 21 | Add more fuzzy objection patterns | LOW | LOW | No | No |
| 22 | Split ai_support.py into smaller handlers | LOW | MEDIUM | No | No |
| 23 | Add load/performance tests | LOW | MEDIUM | No | No |
| 24 | Lint debt cleanup (E501 line-length) | LOW | LOW | No | No |

## P4 — Before Live Send

| # | Step | Risk | Impact | Migration? | Deploy? |
|---|------|------|--------|-----------|---------|
| 25 | Catalog media integration (photos) | LOW | HIGH | No | Yes |
| 26 | Real operator queue UI with assignment | LOW | HIGH | No | Yes |
| 27 | Canary user testing (Stage 3) | MEDIUM | HIGH | No | Yes |
| 28 | Approval workflow testing (Stage 4) | MEDIUM | HIGH | No | Yes |

## P5 — Future Premium

| # | Step | Risk | Impact | Migration? | Deploy? |
|---|------|------|--------|-----------|---------|
| 29 | Photo room analysis (GPT-4V) | MEDIUM | HIGH | No | Yes |
| 30 | Voice transcription (Whisper) | MEDIUM | MEDIUM | No | Yes |
