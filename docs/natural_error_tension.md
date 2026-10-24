# Natural-error tension (D29; A07 calls it D28) — EXPLORATORY

**Status:** exploratory, 0 USD, no new calls. Decision recorded as D29 in `docs/deviations.md`. Readings by Claude Code (single reader, no second coder). Nothing here is a test.

**Question.** On the 35 natural-error items, N1 (cut workflow context) rejects 10/35 and N4 (isolated R4 context) 5/35. On the 50 planted omissions (D25), the direction is the opposite: R1-om 0.64 < R4-om 0.83. What differs?

**Reproduce:** `PYTHONPATH=. .venv/bin/python -m scripts.a07.natural_tension` → `data/derived/rubric/natural_tension_discordant.csv` and `natural_tension_features.csv` (one row per missing record: 44 natural records in the 23 omission/both items, 50 planted). Test: `tests/test_natural_tension.py`.

## 1. Discordant items (single draw per cell)

There are 9 discordant items: 7 rejected only by N1 and 2 only by N4. Three items are rejected by both (rep007_e07, rep023_e05, rep034_e08).

| Item | Error type | D24 | N1 | N4 | Reading (Claude Code) |
|---|---|---|---|---|---|
| rep038_e05, rep038_e08, rep039_e10 | data search | yes | R | A | N1 names `'pending review'` vs `pending_review` in all three. N4 restates the SQL as correct. |
| rep008_e10 | omission (3 records) | ambiguous | R | A | N1 names the three missing patch notes. N4: "all 7 … correctly excluded". |
| rep026_e05 | omission | ambiguous | R | A | N1 quotes the missing refund-reversal record. N4 gives a generic accept. |
| rep026_e10 | omission | no | R | A | Bob **resolved 10 records but saved 9**. N1 catches the resolved-but-unsaved ID (it misquotes the sentence). N4 endorses the exclusion ("lacked a clear effective period"). |
| rep040_e02 | omission (2) | no | R | A | **Wrong reason.** N1 rejects for allegedly extra records without a suspected cause and never names the missing ones. N4 explicitly endorses their exclusion. |
| rep010_e08 | both | yes | A | R | N4 names the mistyped ID (`REC18-` for `REC12-cdbdd8`) and the missing Nia Cole record. N1 gives a generic accept. |
| rep042_e08 | omission | ambiguous | A | R | N4 names the missing Vera record and says Bob's "firm commitment" criterion is not in the instruction. N1 gives a generic accept. |

Net: of the 7 N1-only rejections, 3 are data search, 3 are right-reason omissions (one of them through a visible resolve/save discrepancy), and 1 is wrong-reason. The omission-type split is N1 6/19 vs N4 3/19, which rests on 4 vs 1 discordant omission items.

## 2. Planted versus natural missing records

| Feature (per missing record) | Natural (44) | Planted (50) |
|---|---:|---:|
| (a) sentence in a resolve_records call | 2 | 1 |
| (a) ID in a resolve_records result | 2 | 0 |
| (a) ID in any saved answer | 0 | 0 |
| (b) sentence verbatim in read_source | 44 | 50 |
| (c) first or last source record | 0 | 10 |
| (c) between two included valid records | 39 | 35 |
| (c) relative position, mean | 0.40 | 0.29 |
| Bob's framing or saved reasoning names the record | 9 | 0 (by construction, D25) |
| D24 class (records) | yes 7 / ambiguous 31 / no 6 | not classified; Bob had selected the record himself |

Notes on (a):
- **Natural.** rep010_e08 is a mistyped ID (resolved, then saved as `REC18-`). rep026_e10 was resolved, then dropped.
- **Planted.** rep041_e06: Bob's first resolve call used a truncated sentence and returned `record_id: null`. That failed attempt stays visible in the omission log. The D25 edit removed only his second call's entry.

## 3. What differs (interpretation, not tested)

1. **Different kinds of error.** A planted omission removes a record that Bob himself had judged valid and selected. Bob gives no explanation, and the count is decremented. Natural omissions are mostly Bob's own exclusions on a debatable reading of the criteria (D24: 31 of 44 records ambiguous, 6 no). In 9 records Bob's visible text names them, often with a reason. Where Bob named a missing record, N1 rejected 0 of 7 items and N4 rejected 2 of 7. Where he did not, N1 rejected 6 of 16 and N4 2 of 16.
2. **Position does not explain it.** Natural missing records are never at the edges of the source. They sit between included records at least as often as planted ones (39/44 vs 35/50). Visibility in read_source is complete for both.
3. **The natural reversal is small and partly noisy.** It rests on 7 vs 2 discordant items from single draws at temperature 1.0. Three of the 7 are data search, where the planted contrast says nothing. One N1 rejection is wrong-reason. With paired single draws, the direction is compatible with chance. No test was run, and none was pre-specified.
4. N4's two accepts on items D24 classes "no" (rep026_e10, rep040_e02) agree with Bob's stated reading of the criteria. These verdicts may be defensible rather than misses.

**Caveats:** 35 items, one draw per cell; one reader; feature (a) uses a containment match on sentences; the D24 classes are Claude Code's reading (D24). Planted and natural omissions differ in how they were made, so this comparison is descriptive, not causal.
