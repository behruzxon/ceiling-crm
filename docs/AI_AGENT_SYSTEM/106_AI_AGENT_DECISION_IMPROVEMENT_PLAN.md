# AI Agent Decision Improvement Plan

**Date**: 2026-05-27
**Status**: NOT DEPLOYED, Stage 1 NOT APPLIED

## Top Decision Problems

1. Room-specific design recommendations too generic
2. Installation timeline question not answered
3. "Razmerni bilmayman" not guided well
4. Generic operator intent ("odam kerak") sometimes missed
5. Payment method question not addressed
6. Multi-room calculation not supported
7. Add-on pricing not in calculator
8. "Bugun kelasizmi" must be caught as unsafe promise request
9. Catalog has no photos — user asks "rasm tashla" but gets link only
10. Cyrillic mixed with Latin parsing edge cases

## Prompt / Knowledge Fixes

| Fix | Target File | Risk |
|-----|-------------|------|
| Add installation timeline FAQ | shared/knowledge/uz.md | LOW |
| Add room-specific design recommendations | shared/knowledge/uz.md | LOW |
| Add "razmerni bilmayman" guided response | system_prompt.py | LOW |
| Add payment method explanation | shared/knowledge/uz.md | LOW |
| Strengthen "odam kerak" operator detection | ai_detection.py | LOW |
| Add "bugun kelasizmi" as forbidden promise trigger | system_prompt.py | LOW |

## Deterministic Logic Fixes

| Fix | Target | Risk |
|-----|--------|------|
| Room-based design filter in price calculator | price_calculator_service.py | LOW |
| Add-on pricing estimate | price_calculator_service.py | MEDIUM |
| Multi-room area sum | price_calculator_service.py | LOW |
| "odam" keyword to operator detection | ai_detection.py | LOW |

## Test Packs Needed

- Room recommendation scenarios (10 tests)
- Timeline/ETA question scenarios (5 tests)
- Payment question scenarios (5 tests)
- Multi-room scenarios (5 tests)

## Stage 1 Observation Metrics

After LOG_ONLY apply, track:
- Most common unrecognized intents
- Most common objection types in real traffic
- Price query completion rate (area+design vs clarification)
- Operator request frequency
- Stop request frequency
- Average lead score at operator handoff

## Post-Stage 1 Improvements

Based on Stage 1 data:
1. Optimize prompt for real traffic patterns
2. Add missing FAQ entries
3. Tune objection responses
4. Improve Cyrillic handling if weak spots found
5. Consider GPT-4V for photo analysis
