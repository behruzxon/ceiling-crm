# Project Risk Register

**Date**: 2026-05-27 | **Status**: NOT DEPLOYED

## Risk Table

| # | Risk | Severity | Likelihood | Module | Mitigation | Fix Stage |
|---|------|----------|------------|--------|------------|-----------|
| 1 | F821 globally ignored hides real bugs | HIGH | MEDIUM | CI/Config | Re-enable F821, fix actual undefined names | P1 |
| 2 | Admin web auth disabled by default | HIGH | HIGH | Security | Enable ADMIN_SESSION_AUTH in production | P0 |
| 3 | CSRF disabled by default | HIGH | HIGH | Security | Enable ADMIN_CSRF in production | P0 |
| 4 | No automated DB backup | HIGH | HIGH | Deploy | Add backup script before Stage 1 | P0 |
| 5 | mypy may fail in CI | MEDIUM | HIGH | CI | Fix or configure mypy ignore | P1 |
| 6 | ai_support.py too large (1100+ lines) | MEDIUM | LOW | Bot | Split into smaller modules | P3 |
| 7 | No health check endpoint | MEDIUM | MEDIUM | Deploy | Add /health route | P2 |
| 8 | No async handler behavior tests | MEDIUM | MEDIUM | Tests | Add mocked handler tests | P2 |
| 9 | Catalog has no media | MEDIUM | LOW | Bot | Add photos per design | P4 |
| 10 | No handoff queue web UI | MEDIUM | LOW | Web | Add queue page | P2 |
| 11 | No analytics charts | LOW | LOW | Web | Add chart.js integration | P3 |
| 12 | Remote branch conflicts | MEDIUM | HIGH | Git | Resolve or keep separate branch | P0 |
| 13 | Campaign send code exists | MEDIUM | LOW | Security | Verified gated, but code path exists | P3 |
| 14 | No TLS/nginx config | HIGH | MEDIUM | Deploy | Add reverse proxy | P1 |
| 15 | Handoff auto-expire job missing | LOW | MEDIUM | Scheduler | Add expire job | P2 |
| 16 | No operator queue API endpoints | MEDIUM | LOW | API | Add REST endpoints | P2 |
| 17 | No load/performance tests | MEDIUM | LOW | Tests | Add load test script | P3 |
| 18 | Operator handoff not fully wired into operator.py | MEDIUM | LOW | Bot | Wire service into existing handler | P2 |
| 19 | No photo/voice AI analysis | LOW | LOW | AI | Add GPT-4V/Whisper | P5 |
| 20 | "boshqalar arzon deyapti" still not caught | LOW | LOW | AI | Add more fuzzy patterns | P3 |
