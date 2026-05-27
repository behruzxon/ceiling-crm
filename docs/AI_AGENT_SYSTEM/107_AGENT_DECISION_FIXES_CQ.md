# Step CQ — Agent Decision Fixes

**Date**: 2026-05-27
**Status**: NOT DEPLOYED, Stage 1 NOT APPLIED

## Simulator Findings Applied

### Fix 1: Compare objection phrases expanded

Added 7 new keywords to `_OBJECTION_COMPARE_KW`:
- boshqalar arzon, boshqa joyda arzon, boshqa ustalar arzon
- boshqasi arzon, raqobatchilar arzon, ular arzonroq
- другие дешевле (Russian), бошқалар арзон (Cyrillic Uzbek)

These now classify as "compare" objection instead of being missed.

### Fix 2: Room-specific recommendations added

New section in uz.md: "Xona bo'yicha potolok tavsiyalari"
- Oshxona: moisture-resistant, simple
- Zal/Mehmonxona: decorative, premium options
- Yotoqxona: calm, soft colors
- Bolalar xonasi: bright but not excessive
- Koridor: simple, good with lighting
- Hammom: moisture-resistant PVC

Guidance uses "mos variant" language, never guarantees exact availability.

## Safety Preserved

- No "eng arzon" claims
- No invented discounts
- No fake ETA
- No final price guarantee
- Compare objection response focuses on quality/warranty/value
