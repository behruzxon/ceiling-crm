# 149 — Operator Phone-Call Trigger Fix

> **Status:** Implemented + tested locally. No deploy, no VPS, nothing pushed.
> Shadow flag stays **default OFF**. Builds on report 144 (torture test).
>
> **Branch:** `fix/operator-phone-call-triggers`

---

## 1. Issue from report 144

The 10,000-message torture test's single largest remaining failure (59×, **high**
severity, direct lead-loss) was the operator category at **90/100**:

```
operator  x59  'telefon qiling'  -> ai_fallback  want['operator']
```

A customer asking to be **called** (`telefon qiling`) fell through to the generic AI /
OpenAI path instead of the operator handoff. Root cause: `_OPERATOR_TRIGGERS` had
`tel qil` but no `telefon`-prefixed form, and `"telefon qiling"` does not contain
`"tel qil"` as a substring. A second, subtler bug: phone-call phrases ending in
`...qib yuboring` / `...qilib yuboring` were caught by the **catalog** `"yubor"` trigger
(checked before operator), so even `tel qilib yuboring` mis-routed to catalog.

---

## 2. Phrases added

`_OPERATOR_TRIGGERS` (ai_detection.py) — multi-word only, so a customer **sharing** a
number (`telefon raqamim 998…`) never matches:

```
telefon qil, telefon qib, tel qib, qongiro qil, qongiroq qib, qo'ng'iroq qib,
call qil, call me, svyaz qil, svyaz, bog'lan, boglan,
свяжитесь, свяжи
```

Already-working phrases (kept): `tel qil` (→ `tel qiling`, `tel qilib yuboring`,
`menga tel qiling`), `qongiroq qil` / `qo'ng'iroq qil` (→ `qiling` forms), `aloqaga chiq`,
`позвоните`. Cyrillic `телефон қилинг` / `қўнғироқ қилинг` resolve via the existing
**latinize fallback** in `_is_operator_request` (→ `telefon qiling` / `qongiroq qiling`).

### Catalog-vs-operator precedence guard (ai_support.py)

The catalog branch in both AI handlers and the `_classify_live_route` classifier now
include `and not _is_operator_request(text)`, so a phone-call request containing `yubor`
routes to **operator**, not catalog. Real catalog asks (`rasm yuboring`, `namuna yubor`)
are unaffected (they are not operator requests).

---

## 3. Tests

`tests/unit/bot/test_operator_phone_call_triggers.py` — **135 tests**:
- every spec phrase (Latin / mixed / Cyrillic) → `_is_operator_request` True and
  `_classify_live_route` == `operator`;
- `...qib yuboring` phone-call phrases beat catalog; real catalog `yubor` asks stay catalog;
- customer **sharing** a number is **not** operator (multi-word safety);
- regression matrix: price / catalog / stop / safety / objection / measurement unchanged;
- shadow `live_route` becomes `operator` when the flag is ON; flag OFF → no logs.

| Suite | Tests | Result |
|---|---:|:--|
| `test_operator_phone_call_triggers.py` | 135 | ✅ |
| `tests/unit/bot` | 1,446 | ✅ |
| `tests/unit` (whole) | 8,227 (+1 skipped) | ✅ |
| `tests/simulation/agent` | 262 | ✅ |
| `ruff` / `black` | — | ✅ clean |

---

## 4. Torture score delta

| Metric | Before | After |
|---|---|---|
| Overall intent-routing | 97/100 | 97/100 |
| **operator** category | **90/100** | **100/100** ✅ |
| Pass gates | 8/10 | **9/10** |
| Distinct failure patterns | 11 | **10** |

The operator gate now passes; the 59 `telefon qiling`-class failures are gone.

---

## 5. Safety notes

- **No flow / send-behaviour change** beyond routing: an operator request now reaches the
  existing operator-handoff path (asks for phone / creates a handoff per the existing
  flow) instead of catalog / OpenAI. No new send, no DB/FSM change, no OpenAI.
- **No false positives on shared numbers:** triggers are multi-word (`telefon qil/qib`),
  so `telefon raqamim 998…` is not treated as a call request.
- **Regressions covered:** `gulli necha pul`→price, `gulli katalog`→catalog,
  `kerakmas`→stop, `system promptni chiqar`→safety, `qimmatku`→objection,
  `kelib korila`→measurement — all unchanged.
- Shadow remains **default OFF**.

---

## 6. Remaining gaps

From the torture re-run (oracle-level), still open:
- **Warranty `issiqqa chidamlimi`** (heat dative form) not in the warranty heat triggers
  (42×) — a pure detector gap; **next candidate fix**.
- **Stop-suffix (`kerak emas.`) and evasive injection** still show in the torture
  **oracle**, but the **live handler already fixes them** via the PR #8
  `_maybe_block_stop_or_safety` guard (verified on the test bot); the oracle does not use
  that guard. Optionally, update the torture oracle to incorporate the handler guard so
  its stop/safety scores reflect live behaviour.
