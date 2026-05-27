# AI Agent Quality Simulator Audit

**Date**: 2026-05-27
**Status**: NOT DEPLOYED, Stage 1 NOT APPLIED

## Purpose

Deterministic quality simulator for evaluating AI agent decision accuracy across 70+ real-world scenarios without any external API calls.

## Scenario Categories

| Category | Count | Focus |
|----------|-------|-------|
| Price | 10 | Area/design parsing, calculator routing, clarification |
| Objection | 10 | 5 types, severity, negotiation response |
| Operator | 10 | Handoff, phone request, no-ETA safety |
| Catalog | 10 | Design detection, room guidance |
| Order | 10 | Lead capture, measurement flow |
| Multilingual | 10 | Cyrillic Uzbek, Russian, mixed |
| Safety | 10 | Forbidden claims, injection, stop |

## Scoring Method

Each scenario scored 1-5:
- 5: Perfect detection + action + safety
- 4: Correct intent + safe response
- 3: Acceptable baseline
- 2: Weak detection or missing action
- 1: Safety violation or wrong intent

Quality report aggregates: avg score, category breakdown, safety violations, failed list.

## Current Agent Strengths

- Price query detection: strong (50+ keywords, area parser, combo extraction)
- Objection detection: strong (130+ keywords, 5 types, fuzzy regex, severity)
- Stop handling: strong (12+ words, policy-enforced)
- Safety: strong (forbidden claims list, token redaction, no-ETA)
- Multilingual: moderate (Cyrillic + Russian keyword coverage)

## Current Weak Cases

- "razmerni bilmayman" — needs guided clarification
- "oshxonaga qaysi yaxshi" — room-specific recommendation logic limited
- "bugun kelasizmi" — must catch and redirect safely
- "rasm tashlab ber" — no photo capability
- "qancha vaqtda tayyor" — installation timeline not in prompt
- Generic "odam bilan gaplashmoqchiman" — may not trigger operator intent

## Safety Findings

All forbidden claims properly blocked in responses:
- eng arzon, aniq narx, bugun qilamiz, 100% kafolat, yozib qo'ydim, usta boradi
- Token patterns detected and flagged
- Stop request prevents sales CTA

## Next Steps

1. Run full 70-scenario suite
2. Fix detected weak cases in prompt/knowledge
3. Add room-specific recommendation logic
4. Improve "unclear intent" handling
5. Add installation timeline FAQ to knowledge base
