# DEVLOG 05 — Analysis, paper, and submission checks

## Scope

Pre-specified analysis code and unit tests, statistical validation, interpretation, figures, document assembly, reported numbers, claims-to-source auditing, reproducibility checks, and submission packaging. Cross-reference experimental implementation records as appropriate. See `PROJECT_PLAN.md` §§8.8–8.9, 9.2–9.3, 13, 15, 17.

## Initial state — starter file, not a work entry

No outcome analysis, completed manuscript, or final submission is attested here. Simulation/planning claims in `PROJECT_PLAN.md` must not be mistaken for executed experiment results.

## Entries (append chronologically below)

<!-- Use the entry format in ../CLAUDE.md. Do not overwrite past entries. -->

## 2026-10-24 09:30–09:50 UTC — Claude Code (Opus 5.5), session A03 — Task 3 (build step 5): analysis code, simulation tests, prereg-v1 draft

**Assignment / authorization:** A03 task 3: the full analysis code (plan §§8.6, 8.8), tested on simulated data including a false-positive-rate check; PREREGISTRATION.md and the prereg-v1 materials. **Do not tag prereg-v1.**
**Built or changed:**
- `src/analysis/stats.py`: `sign_flip_test` (cluster sign flips, B = 10,000, seed 2026, p = (1 + #exceed)/(1 + B)), `cluster_bootstrap_ci` (percentile, B = 10,000), `holm`.
- `src/analysis/primary.py`, which covers:
  - loading from runner JSONL; cells as draw means;
  - the primary Δ, and D under gatekeeping with the claim wording and the strong-gap flag;
  - the six-test Holm family; R5 equivalence; cut-artifact check;
  - missing-as-ACCEPT and missing-as-REJECT sensitivities; the `bob_states_condition` sensitivity;
  - the descriptive tables: per variant, discrimination, draw agreement, R6 gate, by episode, natural errors;
  - right-reason detection with a seeded hand-check sample of 20 per variant.
- `src/analysis/meta.py`, `src/analysis/fidelity.py`: level 1 raw rate plus the explained-share diagnostic; level-2 marks.
- `src/analysis/simulate.py`: clearly synthetic data generator.
- `scripts/analysis/run_study1.py`: the single script for all numbers.
- `tests/test_analysis.py` (9 tests).
- `scripts/prereg/make_prereg_files.py` → `data/derived/prereg/`: `main_items.csv` (109), `r1live_subset.csv` (40), `main_run_call_ids.txt` (2,330; SHA-256 `9fc39f00…950d`), `hashes.sha256` (171 files).
- `PREREGISTRATION.md` (draft, untagged).
**Checks performed (all on simulated data, labelled synthetic):**
- Sign flip vs exact enumeration: p = 0.25 for three one-item clusters, p = 0.5 when two items share a cluster (40,000 draws, within 0.01–0.015).
- **False-positive rate of the primary test under H0: 0.057** (300 datasets, real structure of 109 items / 43 trajectories, cluster and item SD 1.0, 2,000 flips; Monte Carlo SE ≈ 0.013).
- Holm FWER under the global null ≤ 0.09 (150 datasets).
- Power for +20 pp > 0.6 (60 datasets).
- The gatekeeping branch and claim wording are consistent in every replicate.
- **Expected precision (D8):** mean 95% CI half-width of Δ is 0.068–0.087 over 8 scenarios. Inline script, output in `scratch/a03/precision_sim.txt` (local); procedure as in `docs/deviations.md` D8 addendum.
- Full suite: 306 passed.
**Decisions (implementation, documented in the code):**
- Cell = mean of the draws present.
- Right-reason markers: for categorical data-search relaxations the added value is used, and an IN list's original values are not a marker.
- The extraction "violated criterion value" is not used (no deterministic definition).
- Level 1 reports the raw share (plan rule) plus the explained share (diagnostic only).
**Did not work:** two weak assertions in my first test draft (one always true, one OR-ed) were replaced by exact checks before commit.
**State / limitations:**
- The analysis has never seen real main-run data. `run_study1.py` was exercised only on simulated data and through the tests.
- `hashes.sha256` includes code, so it must be regenerated at tag time.
**Next:** the pilot (task 4); then the readiness checklist for prereg-v1 (Nick tags).
**Cross-references:** plan §§8.6–8.8, 13, 23.2; `PREREGISTRATION.md`; `docs/deviations.md` D8, D11, D12.

## 2026-10-24 10:58–11:05 UTC — Claude Code (Opus 5.5), session A04 — Task 2: D14 level-1 reporting; prereg-v1 finalized

**Assignment / authorization:** A04 task 2: implement D14 and D15, rerun `make_prereg_files`, run all tests, then tag `prereg-v1` (authorized) and push the commit and the tag.
**Built or changed:**
- `src/analysis/fidelity.py`: `level1` returns `raw_exact_share`, with `passes_plan_rule` referring to it only, and `storage_adjusted_exact_share` (difference exactly −5 × unmatched `resolve_records` items), plus a `storage_adjustment` note naming the evidence. The A03 keys `exact_share` and `explained_share` are kept as aliases.
- `tests/test_analysis.py`: `test_fidelity_level1_raw_and_storage_adjusted` (synthetic records, labelled).
- `PREREGISTRATION.md`, `data/derived/prereg/` regenerated (see the `devlog/03_core_experiment.md` A04 entry).
**Checks performed:** full suite before the tag: `pytest -q` → **312 passed** (115 s; `scratch/pytest_a04_t2.txt`, local). `make_prereg_files`: 109 / 40 / 175 files hashed; call list SHA-256 `9fc39f00…950d` (unchanged from A03).
**D18 note:** no analysis script has been or will be run on main-run outcomes until the natural-error rubric is committed.
**Next:** tag `prereg-v1`.
**Cross-references:** `docs/deviations.md` D14, D18; `PREREGISTRATION.md` §5.

## 2026-10-24 12:40–12:48 UTC — Claude Code (Opus 5.5), session A06 — Task 1: D24 natural-error decidability rubric and lexical overlap

**Assignment / authorization:** `assignments/A06_rubric_analysis_omission.md` (Nick), task 1 (D24). The assignment was committed verbatim first (`ad4505c`, 12:40:51 UTC). No model call; no main-run, R1-live, N1, or N4 outcome was read or computed (D18). The A05 session works in the same tree, so only explicit paths are staged.
**Built or changed:**
- `scripts/a06/dump_natural_errors.py`: reading aid. Writes, per natural-error item, what Alice sees (Bob's Task information, Bob's round-1 framing, the pretty raw log) plus the evaluator result to `scratch/a06/natural/` (local).
- `docs/natural_error_rubric.md`: the rubric (categories, item-level rule, disclosure of the two working rules made explicit during reading), the result table, and observations.
- `data/derived/rubric/natural_error_decidability.csv`: 35 rows with `decidable` and a one-line reason.
- `src/analysis/lexical_overlap.py` → `data/derived/rubric/lexical_overlap.csv`: 185 rows (60 natural-error rows, 125 bait rows; 76 applicable).
- `tests/test_rubric_a06.py` (4 tests).
- `docs/deviations.md`: D24–D26 appended.
**Decisions:**
- Classification by my reading (D24). I read the instruction, the full source (with valid/invalid markers) and the missing/extra sentences for every extraction item, the SQL, the value domains and the reference SQL for the 6 data-search items, and the code, tests and outputs for the 3 code items.
- Item-level rule: yes if any component is yes, else ambiguous if any component is ambiguous, else no.
- The overlap uses the bait builder's word rule unchanged (imported, so `baits_extraction.py`, a prereg-v1 file, is not edited). Not applicable for data search and code, and for one mistyped ID.
**Checks performed:**
- `pytest -q tests/test_rubric_a06.py`: 4 passed. The tests cover:
  - the classification covers exactly the 35 items, and types match;
  - the plan §8.3 example overlap;
  - the overlap equals the saved `overlap_words` of all 26 extraction baits;
  - the CSV is reproducible.
- `python -m src.analysis.lexical_overlap`: summary as in the rubric document.
**Observed (classification):** yes 11 / ambiguous 16 / no 8.
- By type: omission 2/12/5, commission 0/1/2, both 2/2/0, data search 6/0/0, code 1/1/1.
- All 6 data-search errors have one cause: `'pending review'` in Bob's SQL against `pending_review` in the logged value domain.
- Mean lexical overlap: natural missing records 0.09 (n 44), natural extra records 0.00 (n 6), extraction baits 1.15 (n 26; ≥ 1 by construction).
**Did not work:** my first scratch helper was named `src.py` and shadowed the `src` package on import; renamed. Nothing else observed.
**State / limitations:** a single reader (Claude Code) and no second coder. The two working rules (absent element → no; present but debatable → ambiguous) were made explicit during reading; this is disclosed in the rubric.
**Next:** task 2 (preregistered analyses), now permitted by D18.
**Cross-references:** `docs/deviations.md` D18, D24; plan §§8.1, 8.8 (natural-error set).

## 2026-10-24 12:48–13:05 UTC — Claude Code (Opus 5.5), session A06 — Task 2: preregistered analyses (prereg-v1, prereg-v1-r1live) on the main run and R1-live

**Assignment / authorization:** A06 task 2. D18 was satisfied by the rubric commit `d0e8773`. No model call.
**Built or changed:**
- `scripts/analysis/verify_all.py`: the one verification script. It runs the frozen `scripts/analysis/run_study1.py` (prereg-v1 code unchanged) and the frozen `src/analysis/r1live.py`, adds natural errors by D24 class (descriptive), and keeps confirmatory, addendum, and exploratory sections apart. The addendum module (`scripts/analysis/a06_addendum.py`) is picked up when it exists.
- `data/derived/rubric/r1live_readings.csv`: confirming readings by Claude Code (D19.8).
  - I read Bob's first reply after Alice named the bait in all 34 items where she did: 34/34 concessions. The 5 keyword-"mixed" items contain "is correct" only in Bob's assessment of Alice's own work.
  - Flag B: 0 keyword candidates, so nothing to confirm.
- Outputs: `results/summaries/study1_analysis.json`, `results/summaries/verification.json`.
- `tests/test_verify_all.py` (synthetic, labelled).
**Checks performed:**
- `PYTHONPATH=. .venv/bin/python -m scripts.analysis.verify_all` (about 15 s).
- `pytest tests/test_verify_all.py tests/test_analysis.py tests/test_r1live_analysis.py`: 14 passed.
- Discordant items counted independently (inline: `paired(cell(R4,bait), cell(R1,bait))`): 4 items in 4 trajectories, all data search.
**Observed (all from verification.json):**
- **Primary.** Detection R4 1.000, R1 0.977.
  - Δ = +0.023, sign-flip p = 0.121, cluster bootstrap 95% CI [0.004, 0.051]; 109 items, 43 trajectories.
  - Not significant, so D was not tested (gatekeeping). D descriptive +0.023. Claim: "no significant Delta". Strong context gap: no.
  - **Structural note:** only 4 trajectories have d ≠ 0 (all positive), so the smallest attainable two-sided sign-flip p is 2/2^4 = 0.125. The test could not reject. The percentile bootstrap interval excludes 0 because every discordant item has the same sign. Both are reported as is.
- **Secondary** (Holm over 6):
  - R2−R1 and R3−R1: +0.023, p 0.121, p_Holm 0.726;
  - R4−R2, R5−R4, R4n−R4: 0, p 1;
  - R6first−R1: +0.005, p 1.
  - None significant.
- **Missing-verdict sensitivity:** 0 missing, so the results are identical.
- **bob_states_condition sensitivity** (38 items): Δ = 0.
- **Cut artifact:** FR(R0′) − FR(R0) = +0.014, CI [0, 0.031], below the 0.10 mark.
- **False rejections:**
  - R0 0/109; R0′ 0.014; R2 0.028; R3 0.018; R4 0.014; R4n 0.018; R5 0.009;
  - R6: first verdict 0.018, final 0.064 (gate fired on 10 of 107 first ACCEPTs, 5 ended as gate rejects).
- **Draw agreement:** R1 0.972, R0′ 0.972, R4 bait 1.000, R4 correct 0.991.
- **Right-reason (deterministic):** R1 0.92, R2 0.97, R3 0.95, R4 0.92, R4n 0.94, R5 0.95, R6 0.99. The preregistered hand check of 20 per variant has not been done yet.
- **Fidelity:**
  - Level 1: raw exact 0.742 (fails the 0.95 rule), storage-adjusted 0.990, 3 unexplained mismatches.
  - Level 2: original REJECTs rejected 0.714 vs matched ACCEPTs 0.008, difference 0.706, bootstrap lower bound 0.508; marks (a) and (b) met.
- **Natural errors (N1 = workflow cut context, N4 = isolated):**
  - Overall: N1 10/35 = 0.286, N4 5/35 = 0.143.
  - By type: omission 0.316 / 0.158 (19); commission 0.333 / 0.333 (3); both 0 / 0.25 (4); data search 0.5 / 0 (6); code 0 / 0 (3).
  - By D24 class: yes 5/11 vs 3/11; ambiguous 2/16 vs 1/16; no 3/8 vs 1/8.
- **R1-live** (40 items, 26 trajectories):
  - Detection 0.900 vs R1 draw mean 0.988; d = −0.088, p = 0.251, CI [−0.192, 0].
  - Flags 0, so the without-flags result is identical, and the limited-check rule is not triggered. Decision: neither "erodes" nor "rescues".
  - Intermediate: Alice named the bait live in 34/40, Bob conceded in 34/34, final REJECT 33/34. In the 6 items where she did not name it, REJECT 3/6.
  - False-rejection reference: original natural verdicts 0/40 REJECT.
**Did not work:** none observed.
**State / limitations:**
- The right-reason hand-check sample (20 per variant) is not yet read.
- The equivalence reading in `verification.json` is exploratory, and the near-ceiling cells give degenerate [0, 0] intervals.
**Next:** report to Nick (done in the session), then task 3.
**Cross-references:** `PREREGISTRATION.md` §5, `PREREGISTRATION_R1LIVE.md` §3; `docs/deviations.md` D18, D19, D24.

## 2026-10-24 13:24–13:30 UTC — Claude Code (Opus 5.5), session A06 — Tasks 3–4: addendum analysis (D25, D26), exploratory readings, final verification run

**Assignment / authorization:** A06 tasks 3 and 4. The analysis code (`scripts/analysis/a06_addendum.py`) was committed in `8e138ca`, before the first addendum call.
**Checks performed:** `PYTHONPATH=. .venv/bin/python -m scripts.analysis.verify_all` → `results/summaries/verification.json`. Full test suite at `8e138ca`: 470 passed.
**Observed: addendum (outside the Holm family, α = 0.05):**
- **D25 omission baits** (50 items, 31 trajectories; counterparts 22 from the main run and 28 from a06; 0 missing).
  - Detection R1-om 0.64, R4-om 0.83.
  - **Δ_om = +0.19, sign-flip p = 0.0074, CI [0.065, 0.302].** Significant, so D_om was tested.
  - **D_om = +0.18, p = 0.011, CI [0.054, 0.295].**
  - False rejections R0′ 0.02, R4-correct 0.03. Missing sensitivities are identical (0 missing).
  - Descriptive:
    - commission detection R1 0.977 / R4 1.000 (109 items);
    - on the 22 items that have both versions: commission R1 1.00 / R4 1.00 vs omission R1 0.57 / R4 0.91;
    - natural omissions N1 0.316 / N4 0.158 (19 items).
  - Deterministic right-reason on omission REJECTs (removed ID or the full sentence): R1 42/64, R4 50/83. The markers miss partial quotes, as the read sample shows. Not read in full.
- **D26 R5-post** (40 items, descriptive): detection R5-post 0.963, R1 0.988, R1-live 0.900.
  - R5post − R1 = −0.025, CI [−0.061, 0];
  - R5post − R1live = +0.063, CI [−0.013, 0.156];
  - R1live − R1 = −0.088, CI [−0.192, 0].
**Observed: preregistered right-reason hand check** (seeded 20 per variant, read by Claude Code): 140/140 identify the planted error as the reason for rejecting. The deterministic matches were 17/20 in R1, 19/20 in R2 and R3, and 20/20 in R4, R4n, R5 and R6.
**Observed: exploratory:**
- Reading of every deterministic miss among the main-run bait REJECTs: 49/49 right-reason. The markers missed because of punctuation, number format ("$55,000"), the threshold written without its column, or a paraphrase. Readings in `data/derived/rubric/right_reason_readings.csv`.
- P11 disclosure: 22/32 with the plan markers only, 27/32 with the preregistered analysis markers, 30/32 with the R1-live markers.
- Equivalence reading (±0.10): every preregistered contrast lies inside the margin except R1-live − R1 (CI [−0.19, 0]). Several intervals are degenerate [0, 0] at the ceiling.
**Did not work:** none observed.
**State / limitations:** omission detection rests on 50 items from 31 trajectories with a single bait type (one removed valid record). D26 is descriptive only.
**Next:** report to Nick. Paper writing or further analyses are Nick's decision.
**Cross-references:** `docs/deviations.md` D24–D26; `devlog/03_core_experiment.md` A06 run entry.
