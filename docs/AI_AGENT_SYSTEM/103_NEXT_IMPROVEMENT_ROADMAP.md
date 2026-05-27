# Next Improvement Roadmap

**Date**: 2026-05-27

## Immediate Safe Steps (no VPS/deploy needed)

| # | Step | Goal | Risk | Impact |
|---|------|------|------|--------|
| 1 | Create PR from feature/vash-ai-hardening-session | Get code reviewed | LOW | HIGH |
| 2 | Fix CI mypy if failing | Green CI | LOW | HIGH |
| 3 | Wire operator handoff into operator.py handler | Complete queue integration | LOW | MEDIUM |
| 4 | Connect order flow to price calculator | Consistent pricing across flows | LOW | MEDIUM |
| 5 | Add e2e bot flow simulation tests | Catch handler integration bugs | LOW | HIGH |

## Pre-Stage 1 Steps (before LOG_ONLY apply)

| # | Step | Goal | Risk | Impact |
|---|------|------|------|--------|
| 6 | Merge PR to main | Code on main branch | LOW | HIGH |
| 7 | Verify VPS has Docker + postgres + redis | Infrastructure ready | LOW | HIGH |
| 8 | Run alembic upgrade head on VPS | DB schema current | MEDIUM | HIGH |
| 9 | Run preflight scripts on VPS | Verify environment | LOW | HIGH |
| 10 | Create DB backup | Safety net | LOW | CRITICAL |
| 11 | Verify .env has all required vars | No missing config | LOW | HIGH |
| 12 | Enable ADMIN_SESSION_AUTH for web | Basic web security | LOW | HIGH |

## Stage 1 Observation Steps (after LOG_ONLY apply)

| # | Step | Goal | Risk | Impact |
|---|------|------|------|--------|
| 13 | Apply LOG_ONLY preset via /agent dashboard | Start observation | LOW | HIGH |
| 14 | Send 5 test messages to bot | Verify traces | LOW | HIGH |
| 15 | Monitor 30 min active | Check for errors | LOW | HIGH |
| 16 | Monitor 24h passive | Check stability | LOW | HIGH |
| 17 | Review agent traces in DB | Verify pipeline works | LOW | MEDIUM |
| 18 | Check admin group notifications | Verify alerts work | LOW | MEDIUM |

## Post-Stage 1 Strengthening (after real traffic data)

| # | Step | Goal | Risk | Impact |
|---|------|------|------|--------|
| 19 | Analyze real user price queries | Optimize calculator | LOW | HIGH |
| 20 | Analyze real objection patterns | Improve detection | LOW | HIGH |
| 21 | Add web handoff queue page | Operator visibility | LOW | HIGH |
| 22 | Add analytics charts | Visual insights | LOW | MEDIUM |
| 23 | Operator handoff API endpoints | Dashboard integration | LOW | MEDIUM |
| 24 | Campaign send DRY_RUN test | Prepare Stage 2 | MEDIUM | HIGH |

## Future Premium Steps

| # | Step | Goal | Risk | Impact |
|---|------|------|------|--------|
| 25 | Photo room analysis (GPT-4V) | Visual AI | MEDIUM | HIGH |
| 26 | Voice transcription (Whisper) | Audio support | MEDIUM | MEDIUM |
| 27 | Catalog media integration | Rich browsing | LOW | HIGH |
| 28 | Real operator queue UI | Live queue management | LOW | HIGH |
| 29 | AI response quality simulator | Testing AI quality | LOW | MEDIUM |
| 30 | Mobile PWA | Mobile access | MEDIUM | HIGH |

## Recommended Next 10 Steps

1. Create/merge PR (immediate)
2. Fix CI mypy if needed (immediate)
3. Wire operator handoff into operator.py fully (immediate)
4. Add e2e simulation tests (immediate)
5. VPS setup + DB backup (pre-Stage 1)
6. Alembic migrations on VPS (pre-Stage 1)
7. Apply Stage 1 LOG_ONLY (Stage 1)
8. 30min + 24h observation (Stage 1)
9. Web handoff queue page (post-Stage 1)
10. Analytics charts (post-Stage 1)
