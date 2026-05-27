# Step CN — Price Calculator Source-of-Truth Service

**Date**: 2026-05-27
**Branch**: feature/packages-update

## Purpose

Single deterministic price calculator service that all components (AI button, web, CRM) can use for customer-facing estimates.

## Source of Truth

Customer-facing rates: `shared/constants/pricing.py :: DESIGN_PRICES_CUSTOMER`
Internal quote rates: `shared/constants/pricing.py :: DEFAULT_BASE_PRICES` (NOT used for customer estimates)

| Design | Customer Rate (UZS/m2) |
|--------|----------------------|
| Adnatonniy | 80,000 |
| Hi-tech | 120,000 |
| Mramor | 120,000 |
| Naqsh | 120,000 |
| Kosmos | 120,000 |
| Osmon | 120,000 |
| Gulli | 130,000 |
| Qora UF | 140,000 |
| Unknown | 100,000 (default) |

Discount tiers: >20 m2 = 5%, >40 m2 = 10% (automatic, from DISCOUNT_TIERS)

## Area Parser

Supports: 20 kv, 20kv, 20 m2, 20 metr, 5x4, 5 x 4, 5*4, decimals
Rejects: < 1 m2, > 500 m2, no area found

## Design Parser

Aliases: oddiy/matoviy/satin -> adnatonniy, gulli/print/pechat -> gulli, led/shadow -> hi-tech, etc.

## Response Example

```
Taxminiy hisob:
Maydon: 20 m2
Tur: Gulli
Narx: 130 000 so'm/m2
Jami: 2 600 000 so'm

Bu taxminiy hisob. Yakuniy narx o'lchov va material bo'yicha aniqlanadi.
```

## Safety

- All estimates marked is_estimate=True
- Warning: "taxminiy hisob" in every response
- Warning: "Yakuniy narx o'lchov bo'yicha aniqlanadi"
- No "eng arzon" claim
- No fake discount (only area-based automatic tiers)
- No same-day promise
- Token patterns redacted in sanitize
- Internal DEFAULT_BASE_PRICES never shown to customers
