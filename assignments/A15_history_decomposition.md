# A15 — What in the earlier episodes causes omission blindness? (R3t, R3o)
Authorization: Nick Wagner, 25 October 2026. Record as the next free D number in docs/deviations.md, stating: motivated by the A13 result (R2 − R1 = +0.30, R3 − R1 = +0.09 on the D25 omission items); exploratory follow-up; variants, tests and interpretation rows below were fixed before any A15 call. Commit this file (assignments/A15_history_decomposition.md, verbatim), the D entry, the caps change and the analysis script before any live call. Stage a15, cap 6 USD. Nothing else is paid.

## Coordination
Build, test and mock now. Live calls only after A14's launcher (PID 198694) has exited and no scripts.a14 process remains (one background wait, no repeated polling). Explicit git paths only; pull --rebase your own unpushed commits; do not touch A14's files or results.

## Variants (D25 omission items, 50 items; both omission and correct versions)
Both are built from the R3 context (R1 with earlier communication phases removed), with the same builder and the same byte-identity guarantees for everything kept:
- R3t ("earlier work only"): for every earlier episode keep the task phase; remove verdict, feedback and reflection (communication already removed as in R3). Current episode unchanged.
- R3o ("earlier outcomes only"): for every earlier episode keep verdict, feedback and reflection; remove the task phase (communication already removed). Current episode unchanged.
Before building, verify on all 50 items that every earlier episode splits cleanly into these segments with the existing segment boundaries. If any item cannot be split, stop and report; do not substitute items. Record per item and variant the token count, and any residual information (e.g. reflections that mention earlier task content), as was done for R3.

Cells: R3t and R3o × {omission, correct} × 2 draws = 400 calls. Model and parameters as the main run. Order seeded (2026), items permuted, cells per item permuted, item blocks adjacent. Call IDs a15:HIST:<item>:<variant>:<version>:<draw>. Baselines reused, never rerun: R1-om, R0′, R2, R3 and their correct versions from a06/A13.

## Analysis (omission versions; per-item draw means; trajectory clusters)
Primary family, Holm over exactly two, cluster sign-flip (10,000, seed 2026, two-sided) and cluster bootstrap 95%:
- H_out = Detection(R3t) − Detection(R3)   [effect of removing the outcome history]
- H_work = Detection(R3o) − Detection(R3)  [effect of removing the earlier task work]
Gatekeeping per significant test as in plan §8.6: D_i = [y(X, om) − y(X, correct)] − [y(R3, om) − y(R3, correct)]; otherwise D descriptive. Equivalence flag ±0.10 for each.
Secondary, descriptive with intervals: R3t and R3o each versus R1 and versus R2; false rejection per variant versus R0′; detection against removed token count across R1, R3, R3t, R3o, R2 (scatter data, no model fit claimed); named_accept and right-reason per variant; missing-verdict sensitivities.

Interpretation rows (fixed now):
1. H_out significant positive, H_work inside ±0.10: the outcome history (earlier verdicts, rewards, reflections) suppresses omission checking; context length cannot explain it, because the removed segment is short. History-dependent acceptance; a plus-factor candidate. This does not by itself show partner-specificity.
2. H_work significant positive, H_out inside ±0.10: earlier task work drives it; interference or length, not relationship history.
3. Both significant positive: both contribute; report sizes side by side.
4. Neither significant: the R3 − R2 gap needs both segments together (or is not resolved at this n); report intervals.
Any other pattern: state which row comes closest and which condition fails, as in A13.

## Build, run, report
1. src/replay additions for R3t and R3o; scripts/a15/launch_a15.py (A14 launcher pattern, --plan, mock, --live --approved-stage a15; stop guard: STOP on any 429 containing "spending cap", STOP at more than 10 quota 429s in 5 minutes, response_model check); scripts/analysis/a15_addendum.py writing verification.json key addendum.a15; results_tables.py new section. Append stages.a15: 6.0 to configs/caps.yaml.
2. Tests: kept segments byte-identical to R3 (hash per message); removed segments absent; current episode byte-identical to R1; job counts, adjacency, seed; synthetic tests for the Holm pair and gatekeeping. Mock run complete.
3. Stage 1: 3 items, all cells (24 calls), read all by hand before continuing; stop if a context is not what the cell claims.
4. After completion: verify_all, results_tables, full test suite, independent recount from raw lines. Read 5 ACCEPTs and 5 REJECTs per variant on omission versions; for R3o ACCEPTs, note whether the reasoning refers to earlier acceptance, trust, rewards or the partner's track record (quote, do not interpret).
5. Also fix while waiting: find out why the first verify_all run did not write its output (A13 report) and record the cause, or that it is not reproducible.
6. DEVLOG entries, DEVLOG_INDEX.md, commit, push. Report spend, missing verdicts, H_out and H_work with Holm p, D and FR differences, the token-count table, the readings, and which interpretation row applies, in plain words.
Not authorized: any other variant, any rerun of an existing cell, any Haiku call, any change to prereg tags, D25, A13 or A14.
