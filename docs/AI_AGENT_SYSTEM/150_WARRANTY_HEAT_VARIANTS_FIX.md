# 150 — Warranty Heat-Variant Detector Fix

> **Status:** Implemented + tested locally. No deploy, no VPS, nothing pushed.
> Shadow flag stays **default OFF**. Builds on report 144 (torture test).
>
> **Branch:** `fix/warranty-heat-variants`

---

## 1. Issue

The torture run showed a warranty/quality gap (warranty category **94/100**):

```
warranty_quality  x42  'issiqqa chidamlimi'  -> ai_fallback  want['warranty_faq']
```

Heat-resistance questions in their Uzbek **dative/locative/ablative** forms
(`issiqqa`, `issiqga`, `issiqdan`), stove/steam phrasings (`plita yonida`, `issiq bug'`),
and Russian (`жар`/`жарга`) were not in `_WARRANTY_TOPIC_HEAT`, so they fell through to
the generic AI path. (Cyrillic `иссиққа`/`иссиқда` already matched via the `иссиқ`
substring; the gap was the **Latin** forms.)

---

## 2. Phrases added

`_WARRANTY_TOPIC_HEAT` (ai_detection.py) — bare Latin `issiq` covers all case-forms
(`issiqqa`/`issiqga`/`issiqda`/`issiqdan`/`issiqlik`/`issiq xona`/`issiq bug`):

```
issiq, issiqqa, issiqga, issiqdan, issiq xona, issiq bug',
plita yonida, plita, bug', жар, плита
```

`_WARRANTY_TOPIC_DURABILITY` — generic "is it resistant/durable?" so any
`"<X> ga chidamlimi"` routes to warranty:

```
chidamli, chidamlimi, chidaydimi, qo'rqmaydimi, qorqmaydimi,
чидамли, чидамлими, чидайдими
```

**Safety note on `bug'`:** only the apostrophe form is a trigger — bare `bug` would match
`bugun` (today). Verified: `bugun kelasizmi` / `bugun olib keling` do **not** become
warranty.

---

## 3. Tests

`tests/unit/bot/test_warranty_heat_variants.py` — **115 tests**:
- every heat/stove/steam phrase (Latin / mixed / Cyrillic / Russian) →
  `_is_warranty_quality_question` True and route `warranty`; not price/catalog/operator/AI;
- `plita yonida bo'ladimi`, `oshxonada issiq bug' bo'ladi`, `issiqdan qo'rqmaydimi`;
- **false-positive guards:** `bugun …` is NOT warranty;
- existing warranty topics (kafolat / sifat / hid / sog'liq / suv / namlik / sertifikat)
  unchanged;
- regression matrix: price / catalog / operator / stop / safety / objection / measurement
  unchanged;
- shadow `live_route` becomes `warranty` when the flag is ON; flag OFF → no logs.

| Suite | Tests | Result |
|---|---:|:--|
| `test_warranty_heat_variants.py` | 115 | ✅ |
| `tests/unit/bot` | 1,561 | ✅ |
| `tests/unit` (whole) | 8,342 (+1 skipped) | ✅ |
| `tests/simulation/agent` | 262 | ✅ |
| `ruff` / `black` | — | ✅ clean |

---

## 4. Torture score delta

| Metric | Before | After |
|---|---|---|
| Overall intent-routing | 97/100 | **98/100** |
| **warranty_quality** category | **94/100** | **100/100** ✅ |
| Pass gates | 9/10 | **10/10** ✅ |
| Distinct failure patterns | 10 | **9** |

All 10 pass gates now meet target. The 42 `issiqqa`-class warranty failures are gone.

---

## 5. Safety notes

- **No copy / price change:** only the heat/durability detector triggers were extended;
  warranty reply text and prices are untouched. (The `heat` topic reply was already
  present and is reused.)
- **No flow change:** the warranty branch + `_classify_live_route` already use
  `_is_warranty_quality_question`; this PR only widens what that detector matches. No
  `ai_support.py` change was needed.
- **No false positives:** `bug'` is apostrophe-only (`bugun` excluded); `issiq` has no
  common non-heat homograph in this domain; regression matrix is green.
- **No new send / DB / FSM / OpenAI.** Shadow remains **default OFF**.

---

## 6. Remaining gaps

The torture re-run's remaining 9 patterns are all **stop_delay** and **safety**, and are
**oracle-level only**: the torture `_route` oracle uses exact-match `is_stop_signal` and a
regex-only injection check, while the **live handler already fixes** suffixed stops
(`kerak emas.`) and evasive injection via the PR #8 `_maybe_block_stop_or_safety` guard
(verified on the test bot). No remaining **live** detector gap is known from report 144.

**Recommended next step:** update the torture test's `_route` oracle to incorporate the
PR #8 handler guard (`_is_low_interest_stop` + `_is_safety_block`) so its stop/safety
scores reflect the already-shipped live behaviour — closing the last 9 oracle-only
patterns and giving a true end-to-end score.
