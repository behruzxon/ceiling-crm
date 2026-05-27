# Live Test Scenarios

30+ scenarios for canary testing the AI agent system.

## How to use

1. Set flags for the target stage (see `17_CANARY_ROLLOUT_RUNBOOK.md`)
2. Use a canary Telegram account
3. Execute each scenario
4. Check expected behavior in bot + dashboard
5. Mark pass/fail

## Scenario Table

| # | Category | User Action | Expected Signal | Expected Offer | Expected Policy | Dashboard Metric | Pass? |
|---|----------|-------------|-----------------|----------------|-----------------|------------------|-------|
| 1 | Price | "narxi qancha" | wants_price | price_calculation | reply_now | intent: wants_price | |
| 2 | Price+Area | "20 kv qancha" | wants_price, area=20 | price_calc+design | reply_now | area detected | |
| 3 | Price+Dim | "5x4 xona hisobla" | wants_price, area=20 | price_calculation | reply_now | area detected | |
| 4 | Price+Design | "30 m2 gulli qancha" | wants_price, area=30 | price_calculation | reply_now | | |
| 5 | Catalog | "katalog bormi" | wants_catalog | design_help | reply_now | intent: wants_catalog | |
| 6 | Catalog | "dizayn ko'rsating" | wants_catalog | design_help | reply_now | | |
| 7 | Order | "zakaz bermoqchiman" | wants_order | order_continue | reply_now | intent: wants_order | |
| 8 | Order | "buyurtma qilaman" | wants_order | order_continue | reply_now | | |
| 9 | Measurement | "usta chaqiring" | wants_measurement | measurement_visit | reply_now | | |
| 10 | Operator | "operator kerak" | wants_operator | operator_consult | handoff_operator | cancel pending | |
| 11 | Operator | "odam bilan gaplashaman" | wants_operator | operator_consult | handoff_operator | | |
| 12 | Discount | "chegirma bormi" | wants_discount | discount_discuss | reply_now | "operator" in reply | |
| 13 | Price Obj | "qimmat ekan" | objection: price | cheaper_option | reply_now | no "eng arzon" | |
| 14 | Price Obj | "pulim yetmaydi" | objection: price | cheaper_option | reply_now | | |
| 15 | Price Obj RU | "дорого" | objection: price | cheaper_option | reply_now | | |
| 16 | Trust Obj | "kafolat bormi" | objection: trust | warranty_trust | reply_now | | |
| 17 | Trust Obj | "real rasm bormi" | objection: trust | warranty/portfolio | reply_now | | |
| 18 | Trust RU | "гарантия есть?" | objection: trust | warranty_trust | reply_now | | |
| 19 | Not Ready | "keyinroq" | objection: not_ready | design_help | wait_and_observe | no aggressive msg | |
| 20 | Not Ready | "o'ylab ko'raman" | objection: consult | design_help | wait_and_observe | | |
| 21 | Stop | "kerak emas" | stop_request | no_offer | disable_agent | cancel pending, stop signal | |
| 22 | Stop | "yozmang" | stop_request | no_offer | disable_agent | stop signal +1 | |
| 23 | Stop | "stop" | stop_request | no_offer | disable_agent | | |
| 24 | Stop RU | "не надо" | stop_request | no_offer | disable_agent | | |
| 25 | Urgency | "bugun kerak" | urgency: high | fast_install | escalate(warm) | no "bugun qilamiz" | |
| 26 | Urgency | "ertaga kerak" | urgency: high | fast_install | escalate(warm) | | |
| 27 | Cyrillic | "нархи қанча" | wants_price | price_calculation | reply_now | Cyrillic detected | |
| 28 | Cyrillic | "қиммат" | objection: price | cheaper_option | reply_now | | |
| 29 | Typo | "narhi qanca" | wants_price | price_calculation | reply_now | typo corrected | |
| 30 | Mixed | "narx сколько" | wants_price | price_calculation | reply_now | mixed script | |
| 31 | Cold | "salom" | unclear | no_offer | wait_and_observe | no aggressive action | |
| 32 | Cold | "ha" | unclear | no_offer | wait_and_observe | | |
| 33 | Follow-up | catalog view + wait 10min | — | — | schedule_followup | followup pending +1 | |
| 34 | Follow-up | price calc + wait 10min | — | — | schedule_followup | followup pending +1 | |
| 35 | Follow-up | order start + wait 10min | — | — | schedule_followup | followup pending +1 | |

## Safety Checks (verify at every stage)

| # | Check | Expected | Pass? |
|---|-------|----------|-------|
| S1 | "kerak emas" stops all follow-ups | followup_enabled=false | |
| S2 | Cold lead gets no admin escalation | no admin alert | |
| S3 | Non-canary user blocked in canary mode | execution blocked | |
| S4 | Message with phone number blocked | sandbox blocked | |
| S5 | Message with "eng arzon" blocked | sandbox blocked | |
| S6 | Message with "bugun qilamiz" blocked | sandbox blocked | |
| S7 | Daily cap (3) prevents spam | 4th message blocked | |
| S8 | Lifetime cap (5) prevents spam | 6th followup blocked | |
| S9 | Expired approval not executed | status: expired | |
| S10 | Rejected execution not sent | status: rejected | |
