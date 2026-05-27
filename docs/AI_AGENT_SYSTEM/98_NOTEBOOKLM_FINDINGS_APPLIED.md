# Step CJ — NotebookLM Findings Applied

**Date**: 2026-05-27
**Branch**: feature/packages-update
**Prompt Version**: 2026-05-27-cj-notebooklm-hardening

## Accepted Findings

| # | Finding | Action | Target File |
|---|---------|--------|-------------|
| 1 | Gulli price mismatch (uz.md: 120k, should be 130k) | Fixed to 130,000 | shared/knowledge/uz.md |
| 2 | Hi-tech price mismatch (uz.md: 130k, should be 120k) | Fixed to 120,000 | shared/knowledge/uz.md |
| 3 | Bot button knowledge missing | Added "Bot bo'limlari" section | shared/knowledge/uz.md |
| 4 | AI mode buttons missing | Added "AI rejim tugmalari" section | shared/knowledge/uz.md |
| 5 | Order flow incomplete | Added "Buyurtma jarayoni (batafsil)" | shared/knowledge/uz.md |
| 6 | Package details missing | Added "Paketlar / xizmat turlari" | shared/knowledge/uz.md |
| 7 | Operator ETA undefined | Added "Operatorga ulash qoidasi" | shared/knowledge/uz.md |
| 8 | Payment rules missing | Added "To'lov qoidasi" | shared/knowledge/uz.md |
| 9 | Forbidden claims not listed | Added "Taqiqlangan gaplar" (8 items) | shared/knowledge/uz.md |
| 10 | Discount rules unclear | Added "Chegirma qoidasi" | shared/knowledge/uz.md |
| 11 | Prices not labeled taxminiy | Added TAXMINIY warning after price table | shared/knowledge/uz.md |
| 12 | No button/flow guidance in prompt | Added BUTTON/FLOW section | system_prompt.py |
| 13 | No price safety block in prompt | Added NARX XAVFSIZLIGI section | system_prompt.py |
| 14 | No order/operator safety in prompt | Added BUYURTMA/OPERATOR XAVFSIZLIGI | system_prompt.py |
| 15 | No prompt version | Added PROMPT_VERSION constant | system_prompt.py |

## Deferred Findings

| # | Finding | Reason | Future Step |
|---|---------|--------|-------------|
| 1 | Dynamic promotions not in KB | Requires business input | Step CK |
| 2 | Photo/voice analysis | Requires new feature | Step CL |
| 3 | Package exact prices (VIP/Standard) | Business not yet defined | When defined |
| 4 | Operator queue/ETA system | Requires new feature | Step CL |
| 5 | DEFAULT_BASE_PRICES vs DESIGN_PRICES gap | Intentional (internal vs customer) | No change |

## Price Source-of-Truth

| Design | DESIGN_PRICES_CUSTOMER | uz.md (fixed) | system_prompt | Match |
|--------|----------------------|---------------|---------------|-------|
| Adnatonniy | 80,000 | 80,000 | 80,000 | YES |
| Hi-tech | 120,000 | 120,000 | 120,000 | YES |
| Mramor | 120,000 | 120,000 | 120,000 | YES |
| Gulli | 130,000 | 130,000 | 120-140k range | YES |
| Qora UF | 140,000 | 140,000 | 140,000 | YES |
| Kosmos | 120,000 | 120,000 | 120,000 | YES |
| Osmon | 120,000 | 120,000 | 120,000 | YES |

Source of truth: `shared/constants/pricing.py :: DESIGN_PRICES_CUSTOMER`
Internal quotes (DEFAULT_BASE_PRICES) intentionally higher — not shown to customers.

## Changed Files

1. `shared/knowledge/uz.md` — 8 new sections, 2 price fixes, taxminiy warning
2. `apps/bot/ai/system_prompt.py` — 3 new safety blocks, PROMPT_VERSION added

## Safety Improvements

- Explicit forbidden claims list in uz.md (8 items)
- Price safety block in system prompt (taxminiy, no final/aniq narx)
- Order/operator safety block (no yozib qo'ydim, no fake ETA)
- Button/flow guidance (redirect to correct flows)
- Chegirma rules (no invented discounts)
- Payment rules (no Payme/Click claim)

## Behavior Changed

- Bot handler behavior: NO
- Catalog behavior: NO
- Button texts: NO
- Callback patterns: NO
- Flags: NOT ENABLED
- Stage 1: NOT APPLIED
- AI prompt content: YES (safety hardening only, no behavior change)
- Knowledge base content: YES (sections added, prices fixed)
