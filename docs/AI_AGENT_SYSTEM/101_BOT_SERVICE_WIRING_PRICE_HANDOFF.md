# Step CO — Bot Service Wiring (Price Calculator + Operator Handoff)

**Date**: 2026-05-27
**Branch**: feature/packages-update

## Price Calculator Wiring

- When user sends area+design (e.g. "20 kv gulli"), PriceCalculatorService provides deterministic estimate
- No OpenAI call needed for complete area+design input
- Falls back to existing _show_price_upsell if calculator unavailable
- Memory payload saved to FSM state (last_price_estimate)
- Response includes "taxminiy" warning and measurement finalization note
- Lead scoring preserved (+15 area, +10 district)

## Operator Handoff Wiring

- AI operator button creates handoff queue entry via CRMOperatorHandoffService
- Checks phone status from AI memory
- Returns safe message (no fake ETA)
- Falls back to existing operator prompt on any error
- Queue recording only if CRM_OPERATOR_HANDOFF_QUEUE_ENABLED=true
- Admin notify only if CRM_OPERATOR_HANDOFF_ADMIN_NOTIFY_ENABLED=true (default OFF)

## Safety

- No fake ETA, no "hozir", no "bugun"
- No "eng arzon", no fake discount
- All estimates marked taxminiy
- Service errors never crash bot — fallback to existing behavior
- Stop words still win before any service call
- Double-reply prevention preserved
