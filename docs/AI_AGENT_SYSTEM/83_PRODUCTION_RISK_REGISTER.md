# Production Risk Register

| # | Risk | Severity | Current Mitigation | Before Stage 1? | Before Stage 2? | Before Production? |
|---|------|----------|-------------------|-----------------|-----------------|-------------------|
| 1 | Migrations not applied | HIGH | Checklist step | YES | YES | YES |
| 2 | No DB backup before migrate | HIGH | Checklist step | YES | YES | YES |
| 3 | Session auth disabled | LOW | Default OFF, HTTP Basic works | NO | Optional | YES |
| 4 | Campaign send disabled | LOW | Default OFF | NO | NO | Staged |
| 5 | Operator reply disabled | LOW | Default OFF | NO | NO | Staged |
| 6 | DB RBAC disabled | LOW | Default OFF, env fallback | NO | S2 stage | YES |
| 7 | ai_support.py still 1035 lines | LOW | Refactored from 1356, sibling modules | NO | Optional | Optional |
| 8 | No real bot canary test | MEDIUM | Dry-run + unit tests | YES (5 msgs) | YES (canary) | YES |
| 9 | No VPS deployment test | MEDIUM | Local smoke + import tests | Before deploy | YES | YES |
| 10 | No production DB backup plan | HIGH | Manual backup checklist | YES | YES | YES |
| 11 | Real Telegram send possible if flags ON | MEDIUM | All send flags OFF, confirmation required | NO (flags OFF) | Canary only | Staged |
| 12 | IP enforcement could lock out | LOW | Default OFF, fallback enabled | NO | NO | S7 only |
| 13 | CSRF not enabled | LOW | Default OFF, foundation ready | NO | S4 | YES |
| 14 | Large migration chain (42 files) | LOW | Linear chain, tested imports | Before apply | N/A | N/A |
| 15 | No monitoring/alerting in prod | MEDIUM | Manual observation + logs | Acceptable | Setup needed | YES |

## Summary

- **Critical risks:** 0 (all mitigated)
- **High risks:** 3 (migrations, backup, backup plan — all checklist items)
- **Medium risks:** 3 (canary, VPS, monitoring — acceptable for Stage 1)
- **Low risks:** 9 (all default OFF or optional)

## Verdict

**CONDITIONAL GO** — proceed to Stage 1 LOG_ONLY after completing checklist items 1, 2, 8.
