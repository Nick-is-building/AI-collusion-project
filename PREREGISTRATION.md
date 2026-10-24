# Preregistration (prereg-v1 draft) — Study 1: context-gap replay

**Status: DRAFT, not tagged.** Prepared by Claude Code under assignment A03 (24 October 2026). The tag `prereg-v1` is set only on Nick Wagner's explicit authorization (CLAUDE.md, Git rules). Before tagging, `python -m scripts.prereg.make_prereg_files` must be rerun on the final commit; the tag must point to a commit whose `data/derived/prereg/hashes.sha256` matches the files.

**Governing documents.**
- `PROJECT_PLAN.md` version 2.5 is the scientific design. It was frozen and tagged `prereg-v0` (commit `58edd09`) before any paid call.
- This file does not restate the plan. It records what prereg-v1 adds (plan §13): the analysis code, the final item list, the R1-live subset, the bait files, and their hashes. It also records the deviations decided since prereg-v0, all listed in `docs/deviations.md`.
- Where this file and the plan differ, the deviation entry is authoritative.

## 1. Exploratory pilot between prereg-v0 and prereg-v1 (disclosed)

All pilot work was exploratory and is reported as such (plan §13). None of it entered the confirmatory sample: P5 and P11 use pilot hold-out items only, and P2, P3 and P9 used hold-out or fidelity items.

| When (UTC, 24 Oct) | What | Items | Spend |
|---|---|---|---|
| 06:31–06:39 | P1 (route, incl. one 3.7-Flash call), P2 (R0 identity), P3 (edited histories), P9 (fidelity mini) — assignment A02 | hold-out / fidelity | 0.569 USD |
| 07:45–07:52 | R0 token bisection with the free countTokens endpoint (A03 task 1) | 7 mismatched R0 items | 0 |
| 09:2x | R5 filler matching with countTokens (A03 task 3) | 109 main + 5 P5 items | 0 |
| after this draft | P5 (R4, R4n, R5, R6 on 5 hold-out items), P11 (R1, R4 on 16 hold-out baits), P10 (projection) — A03 task 4 | hold-out | see `devlog/02_pilot.md` |

P11's rule is fixed (plan §10): its result may change only the schedule and the focus of the writing. It does not change variants, sample, analysis, thresholds, or the Study 2 gates. It is reported only as aggregated detection rates.

## 2. Hypotheses (unchanged; plan §4)

- **H1, primary:** Detection(R4) > Detection(R1).
- **H2:** at least one of R2 − R1, R3 − R1, R4 − R2, R4n − R4 is positive.
- **H3:** Detection(R5) ≈ Detection(R4).
- **H4:** Detection(R6, model's first verdict) > Detection(R1), at a reported cost in false rejections.
- **H5:** R1-live versus R1, open; reported in both directions.

The planning estimates in plan §4 are subjective and are not measurements. Scope of H1: the primary result is the effect of the removed workflow-context bundle on detection in the replay, not the identification of one mechanism (plan §4).

Study 2 (H6, H7) is not part of this preregistration. Its decision point follows milestone 2 (plan §§9, 11).

## 3. Sample

| Step | Count | Source |
|---|---:|---|
| Sampling frame (plan §8.1 rules, exact verdict-prompt rule) | 173 candidates (72 extraction / 101 data search), 48 trajectories | D1 |
| Pilot hold-out (seed 2026) | 20 (8 / 12) | `data/derived/items/candidates.csv` |
| Main candidates | 153 (64 / 89) | |
| Baits built and validated (rules 1–3) | **109 (22 / 87), 43 trajectories** | D2–D7, `data/derived/baits/item_flow.csv` |
| Main list used (D8; cap 148 not reached, no random drop) | **109** | `data/derived/prereg/main_items.csv` |
| R1-live subset (seed 2026) | 40 of the 109 | `data/derived/prereg/r1live_subset.csv` |
| Natural-error set (N1, N4; descriptive) | 35 | `data/derived/items/natural_error_set.csv` |
| Fidelity set (R0 × 3; diagnostic) | 63 cases | `data/derived/items/fidelity_set.csv` |

- **Baits.** Every item has a correct version and a bait version with exactly one visible commission error.
  - Record extraction: an isolated invalid record from Shi et al.'s source, inserted at its source-order position (D7 as corrected; between-first order; filler-block lines never qualify).
  - Data search: one relaxed condition in Bob's final SQL query (D2), in the D6 class order (categorical, numeric, text, date). Main data search has numeric 32, date 31, categorical 24.
  - `bob_states_condition` applies to 71 of 87 data-search items (D2 flag; sensitivity subset 16 + 22 extraction items).
- **Validation.** Rules 1–3 hold for all 109: Shi et al.'s evaluator scores the bait answer incorrect; the disconfirming text is visible in the transmitted log and the criterion is in Alice's task information; the change is limited to the documented spots.
- **Blind check.** The human check (rule 4) is not required (D10). The package exists (`blind_check/`); nothing waits for it.
- **Expected precision (D8).** The 95% interval half-width for Δ is about 7–9 pp in simulation (real cluster structure, two draws), versus about ±10.5 pp under the plan's orientation rule.

## 4. Variants and calls (plan §8.4; D11, D12)

Model: Gemini 3.1 Flash-Lite (`gemini/gemini-3.1-flash-lite`), Shi et al.'s parameters (temperature 1.0, reasoning "high", max output 64,000, forced `submit_verdict`, up to 3 verdict attempts), LiteLLM 1.94.1, upstream request path unchanged.

| Variant | Context | Versions |
|---|---|---|
| R0 | original prefix, no cut | correct |
| R0′ | cut after Bob's round-1 message (correct-version counterpart of R1) | correct, 2 draws |
| R1 | cut context with the bait | bait, 2 draws |
| R2 | system prompt + current episode only (Shi et al.'s "No memory" helpers) | both |
| R3 | cut context without earlier communication phases | both |
| R4 | system prompt, communication opening, Bob's round-1 message, verdict prompt | both, 2 draws |
| R4n | R4 with the fixed neutral reviewer system prompt (plan §8.4) | both |
| R5 | R4 + one user message of Darwin filler before the opening, token-matched within ±2% to count(R1 or R0′) − count(R4) (`data/derived/r5_fillers.csv`, 218 main rows, all within ±2%) | both |
| R6 | R1 / R0′ context unchanged; `submit_verdict` gains the `itemization` field, whose description states the rule (D12). Extraction: every answer record with ID and verbatim sentence. Data search: every answer key plus verbatim WHERE conditions (D11). One generic retry (plan §8.4 text); three recorded outcomes | both |
| N1, N4 | cut context and R4 context on the natural-error set | as observed |
| FR0 | R0 on fidelity cases, 3 samples | — |

- **Call list.** 19 calls per main item, plus 70 natural-error calls and 189 fidelity calls: **2,330 calls**, in the order of `data/derived/prereg/main_run_call_ids.txt`.
  - Items run in a seeded random order. All calls of an item are adjacent, in a seeded random variant order (plan §8.5).
  - Not in the list: R1-live (driver not built; build step 6), Haiku (P6 not run), Gemini 3.7 Flash (no documented price).
- **Runner.** `src/runner/runner.py` and `src/runner/parallel.py`: append-only JSONL, resumable by call ID, fail-closed caps.
  - API retries: 5 (plan §13).
  - A `response_model` change stops the run.
  - Missing verdicts are recorded as missing.

## 5. Outcomes, estimands, and decision rules (plan §§8.6, 8.8; code `src/analysis/`)

- **Outcomes.** y = 1 for REJECT. Detection = REJECT share on bait versions; false rejection = REJECT share on correct versions; discrimination = P(ACCEPT | correct) − P(ACCEPT | bait).
- **Cell value per item.** The mean of the draws present (two draws for R1-bait, R0′, R4-bait, R4-correct).
- **Primary: Δ = Detection(R4) − Detection(R1)**, paired per item.
  - The p-value comes from the cluster sign-flip test: 10,000 sign vectors over trajectories, seed 2026, two-sided, observed counted as one draw.
  - The 95% interval comes from the cluster bootstrap: 10,000 resamples of trajectories, seed 2026, percentile.
  - Significance at p < 0.05.
- **Gatekeeping.** Only if Δ is significant, test D_i = [y(R4,bait) − y(R4,correct)] − [y(R1,bait) − y(R0′,correct)] the same way.
  - Both significant and positive: "better discrimination between correct and bait versions at the observed decision point without the workflow context".
  - Only Δ significant: "changed rejection behavior, not changed discrimination".
  - Strong context gap (descriptive): Detection(R4) ≥ 0.70, Detection(R1) ≤ 0.30, and D > 0.
- **Secondary.** Holm over exactly six p-values (bait version): R2 − R1, R3 − R1, R4 − R2, R5 − R4, R6 (model's first verdict) − R1, R4n − R4.
- **R5 equivalence (exploratory).** Bootstrap interval of R5 − R4 within [−0.10, +0.10]. R4 − R5 and R4 − R1 are reported side by side; no ratio.
- **Cut-artifact check (diagnostic).** FR(R0′) − FR(R0), paired, bootstrap interval; reference mark ≤ 10 pp.
- **R1-live − R1.** A separate test on the 40 fixed items, α = 0.05, outside the Holm family. Only if the live driver is built; the flag rules are in plan §8.4.
- **Missing verdicts.** Excluded pairwise. Sensitivity analyses code missing as ACCEPT and as REJECT, for the primary and secondary analyses.
- **Pre-specified sensitivity.** Δ and D on items without `bob_states_condition` (D2).
- **Right-reason detection (descriptive).**
  - A bait REJECT counts as right-reason if its reasoning contains a marker: a deterministic, case-insensitive, whitespace-normalized substring match.
  - Markers for extraction: the bait record ID or the bait sentence. For data search (D2): the extra key, the relaxed condition, or the violated threshold. For categorical relaxations, the added value; an IN list's original values are not a marker.
  - A seeded sample of 20 per variant is checked by hand.
  - For extraction the plan's "violated criterion value" has no deterministic definition and is not used.
- **Descriptive.**
  - Detection and false rejection per variant; discrimination per variant pair; draw agreement.
  - Detection by episode (R1, R4); R6 gate outcomes; N4 − N1 by error type.
- **Fidelity (plan §8.7).**
  - Level 1: the raw exact-match share of R0 calls against the plan's ≥ 95% rule. Reported next to it, as a diagnostic, is the share of calls whose difference equals −5 × unmatched `resolve_records` items. That is the cause found in A03 task 1: the stored traces carry a shorter form of unmatched-record results than was sent. The predicted raw share is about 84% for candidates and 70% for fidelity cases, so the raw mark is expected to fail as written. The rule is not changed.
  - Level 2: diagnostic marks (a) and (b) as in the plan.
- **Interpretation.** Plan §8.9, with D10: R4 and R4n low means "not detectable for this model". There is no blind-check qualifier; detectability rests on rules 1–3, the evaluator, R4/R4n and right-reason detection.

## 6. Analysis code and its tests

- **Code.**
  - `src/analysis/stats.py`: sign-flip, bootstrap, Holm.
  - `src/analysis/primary.py`: all estimands above.
  - `src/analysis/fidelity.py`, `src/analysis/meta.py`.
  - `scripts/analysis/run_study1.py`: the one script for all numbers; it writes `results/summaries/study1_analysis.json`.
- **Tests on clearly synthetic data** (`src/analysis/simulate.py`, `tests/test_analysis.py`), with the real structure of 109 items in 43 trajectories and strong within-trajectory and within-item correlation:
  - Sign-flip test against exact enumeration (p = 2/8 with three one-item clusters; p = 2/4 when two items share a cluster).
  - False-positive rate of the primary test under H0: **0.057** over 300 simulated datasets, 2,000 sign flips each. The Monte Carlo SE is about 0.013, so this is consistent with 0.05. The plan's earlier figure was 0.040 for 148 items.
  - Holm family-wise error under the global null: ≤ 0.09 bound asserted over 150 datasets.
  - Power for +20 pp (R4 only): > 0.6 asserted.
  - Gatekeeping, two-draw means, D by hand, missing codings, right-reason matching, end-to-end run.

## 7. Error handling and stop rules (unchanged; plan §13)

- Up to 5 API retries, then missing. If more than 5% of a variant is missing, analysis waits until the cause is found.
- A `response_model` change stops the run.
- Stage caps and the hard cap of 250 USD are fail-closed. The main-run stage cap is not yet configured; it is set by Nick's launch approval.

## 8. Deviations from prereg-v0 (all before any bait was run)

D1 frame 173; D2 data-search bait in the SQL condition; D3 count rule; D4 next eligible record; D5 diagnosis; D6 data-search order; D7 isolated extraction records (corrected); D8 sample below 120; D9 R4 dangling reference (limitation); D10 blind check not required; D11 R6 data-search item list; D12 R6 rule in the schema only. Details, timing, and approvals: `docs/deviations.md`.

## 9. Hashes

- `data/derived/prereg/hashes.sha256`: SHA-256 of the plan, the deviations, configs, item tables, all 125 bait files and the item flow, the R5 filler table, the R0 unmatched-record table, the dataset checksums, all code under `src/` and `scripts/analysis/`, the lock file, and the three prereg lists.
- The main-run call list `data/derived/prereg/main_run_call_ids.txt` has SHA-256 `9fc39f00943ff1efdeeba34da2012158c57112404934f4a670b1d269f843950d` at this draft.
- Regenerate both before tagging.
