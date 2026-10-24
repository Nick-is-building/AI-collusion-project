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
