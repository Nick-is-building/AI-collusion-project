# DEVLOG index — topic map, not a history summary

**Purpose:** Find the complete records needed for a Claude Code session without repeatedly loading unrelated DEVLOG blocks. No information is intentionally discarded. Do not use this index as evidence that a task was completed.

**Initial state:** Starter structure only. No Claude Code work is logged in these blocks yet. `PROJECT_PLAN.md` is version 2.5 (final for implementation, frozen; changes only as documented amendments). The researcher's own setup steps are recorded in `devlog/01_foundation.md`. `PROJECT_PLAN.md` documents earlier design discussions and reanalysis, but the files, checks, and outcomes it describes must be inspected/reproduced before being represented as independently confirmed here. Nothing in this index authorizes a run.

## Where to look

| Block | Topic / when to read | Current status |
|---|---|---|
| [`devlog/01_foundation.md`](devlog/01_foundation.md) | Repository setup, dependencies, upstream pinning, pre-sprint artifact intake and provenance, baseline verification, shared infrastructure | A01 tasks 0–2 done (prereg-v0, env, data provenance, Study 0 reproduced); A02 LICENSE check |
| [`devlog/02_pilot.md`](devlog/02_pilot.md) | Technical pilots, cost/timing measurements, feasibility checks, problems, go/no-go recommendations | A02: live P1, P2, P3, P9 (0.57 USD). A03: R0 mismatch cause found (task 1); P5, P11, P10 (task 4). A04: R6 rerun after D13 (task 1) |
| [`devlog/03_core_experiment.md`](devlog/03_core_experiment.md) | Study 1: context reconstruction, bait generation, replay, controls, fidelity, R1-live, model comparison | A01 tasks 3–7; A02 D2–D4; A03: D6/D7 baits (109 main), blind-check package (tablet), R5, R6, N1/N4, job lists, parallel runner |
| [`devlog/04_hysteresis.md`](devlog/04_hysteresis.md) | Study 2: branching trajectories, channel changes, partner intervention, run validity, persistence analyses | A04 task 5: implementation plan (`docs/study2_implementation_plan.md`). A05: build, P8, n = 50 (D21), prereg-study2, main run launched 13:16 UTC; ended 218/250, 32 C′ arms (rep014–045) failed on the AI Studio spend cap; diagnosis entry 2026-10-24 ~21:00 UTC, rerun decision pending (Nick) |
| [`devlog/05_analysis_submission.md`](devlog/05_analysis_submission.md) | Statistical implementation, result validation, figures, paper, reproducibility and submission checks | A03: analysis code + simulation tests, PREREGISTRATION.md draft. A04: D14, prereg-v1 tagged; no outcome analysis before the natural-error rubric (D18). A06: analyses, D25/D26. A07: D28 R6s analysis, D29 note, paper figures; A08: D30/D31 analysis, Figure 4 update, `paper/results_tables.md` |

## Reading and linking rules

1. On session entry, read this index and the complete `PROJECT_PLAN.md`, then the relevant DEVLOG block(s) **in full**. Read necessary older blocks when they contain dependencies, design decisions, or prior failures. Do not treat "not active" as "irrelevant" when the assignment depends on it.
2. Append new records to the **primary topic block**, never to this index. For work spanning blocks, add explicit links and entry headings rather than copying the same long record everywhere.
3. Update the table's *Current status* conservatively when work actually begins/completes. Status is for navigation only; verify details in the referenced entries and repository.
4. Claude Code may add new blocks, folders, or subtopics on its own if the structure warrants it. Update this index immediately, with clear labels and links; preserve existing history.
5. Keep an **Active work and cross-references** section updated with pointers, not compressed narratives. Remove stale pointers when tasks finish, but leave all historical log entries intact.

## Active work and cross-references

- **A06 (done, `assignments/A06_rubric_analysis_omission.md`):** D24 rubric (`docs/natural_error_rubric.md`); preregistered analyses and the addendum via the one script `scripts/analysis/verify_all.py` → `results/summaries/verification.json`; D25 omission baits `data/derived/omission_baits/`, D26 `data/derived/r5post_fillers.csv`; addendum runs `results/raw/a06-*.jsonl` (2.41 USD); readings in `data/derived/rubric/`. Entries in `devlog/05_analysis_submission.md` and `devlog/03_core_experiment.md`. D18 satisfied.
- **A07 (done, `assignments/A07_countermeasure_naturals_figures.md`):** Nick's "D27"/"D28" recorded as **D28** (R6s, with the sentence-only amendment) and **D29** (natural-error tension) in `docs/deviations.md`. R6s code `src/replay/r6s.py`, launcher `scripts/a07/launch_r6s.py`, runs `results/raw/a07-*.jsonl` (2.96 USD), analysis `scripts/analysis/a07_addendum.py`. D29 note `docs/natural_error_tension.md` (`scripts/a07/natural_tension.py`). Figures: `scripts/analysis/figure_data.py` (into `verification.json`) → `scripts/analysis/figures.py` → `paper/figures/` (Study 2 slot). Entries in `devlog/03_core_experiment.md` and `devlog/05_analysis_submission.md`.
- **A08 (done, `assignments/A08_exhaustive_classification.md`):** D30 (R6x exhaustive source classification) and D31 (R6 on the omission items' correct versions) in `docs/deviations.md`. Code `src/replay/r6x.py`, launcher `scripts/a08/launch_r6x.py`, runs `results/raw/a08-*.jsonl` (3.57 USD), analysis `scripts/analysis/a08_addendum.py` (`verification.json` → `addendum.D30_D31_R6x`). Results tables: `scripts/analysis/results_tables.py` → `paper/results_tables.md` (generated; every number with its key). Entries in `devlog/03_core_experiment.md` and `devlog/05_analysis_submission.md`.
- **Assigned work:** A04 done (`assignments/A04_prereg_launch_r1live.md` + `assignments/A04_addendum_D17_D19.md`, incl. Nick's correction): prereg-v1 and prereg-v1-r1live tagged; main run complete (2,330/2,330); R1-live complete (40/40); Study 2 implementation plan written (not built). A01–A04 done. Next: natural-error rubric (D18), then analysis; Study 2 build (Nick).
- **Study 2 (A05, `assignments/A05_study2_build_launch.md`):** code `src/hysteresis/` (run_arm, status_line, guard, partner_control, scheduler, analysis, mock_model, upstream_tree), `scripts/study2/` (launch, monitor, fix_n, run_list, analyze, interrupt_check.sh); tests `tests/test_study2_*.py`; decisions D20–D23 in `docs/deviations.md`; caps `stages.study2`, `check_groups.study2_p8`; runs under `results/study2/<group>/repNNN/<arm>/`, logs `logs/study2/`; upstream copy `work/study2/upstream` (local, reproducible).
- **Active blocks:**
  - `devlog/02_pilot.md`: A04 task-1 entry (R6 rerun); P7 entry;
  - `devlog/03_core_experiment.md`: A04 entries (D15, launcher, main run, R1-live driver);
  - `devlog/05_analysis_submission.md`: A04 task-2 entry (D14, prereg-v1);
  - `devlog/04_hysteresis.md`: A04 task-5 plan entry; Study 2 main-run failure diagnosis (`scripts/study2/diagnose_failures.py` → `results/summaries/study2_main_failure_diagnosis.json`).
- **Deviations:** `docs/deviations.md` D1–D31 (D20–D23 and D27 Study 2; D24–D26 A06; D28–D29 A07; D30–D31 A08); older note: D1–D19 (D13–D16 from A04; D17–D19 from the A04 addendum; **D17 withdrawn** by Nick's correction, entry at the end of the file). All were decided before any main-run call.
- **Preregistration:** `PREREGISTRATION.md`, tag `prereg-v1` (`21f4a0f`); materials in `data/derived/prereg/`. R1-live addendum `PREREGISTRATION_R1LIVE.md`, tag `prereg-v1-r1live` (`74b6277`).
- **Analysis order (D18):** no analysis script on main-run outcomes until the natural-error rubric is committed; only `scripts/main/monitor.py` (operational).
- **Raw run evidence:** `results/raw/*.jsonl` (committed; main run `main-*.jsonl`, R1-live `r1live-*.jsonl`, P7 `pilot-20261024T110912Z-4101d5.jsonl`); countTokens log `results/token_counts/counts.jsonl` (committed); request payloads in `results/requests/` (local, hashed); launch logs in `logs/` (local).
- **Blind check:** `blind_check/` (INSTRUCTIONS.md, ANSWERS.md, 20 pair files, key hash); key `blind_check/key.local.json` local only. Optional per D10.
- **Code map:**
  - `src/replay/`: traces, variants (R0, CUT, R2, R3, R4, R4n), r5, r6, request, token_count, item_tables, dry_run, bait_common, baits_extraction, baits_data_search, build_baits, live_driver (R1-live).
  - `src/runner/`: runner, costs, estimates, item_lists, jobs, parallel; pilot scripts in `scripts/pilot/` (P1–P3, P5, P7, P9–P11); main run in `scripts/main/` (launch_main, monitor).
  - `src/analysis/`: stats, primary, fidelity, meta, simulate; `scripts/analysis/run_study1.py`.
  - Also `scripts/a03/` (bisection), `scripts/prereg/`, `src/reanalysis/`, `src/blind_check/`.
  - Derived tables in `data/derived/`; local scratch in `scratch/` (git-ignored).
- **Relevant dependencies:** `PROJECT_PLAN.md` (complete approved design as supplied; do not silently modify); initial technical setup and all claims of reproduced prior work belong in `01_foundation.md` once actually checked.
- **Pending decisions for Nick:**
  - the natural-error decidability rubric (next assignment, D18); until then no outcome analysis;
  - Study 2: budget conflict with plan §12, RAW LOG PART mapping, project rate limits (AI Studio), Study 2 preregistration (`docs/study2_implementation_plan.md`);
  - untracked Study 2 files from another session (`src/hysteresis/`, `scripts/study2/`, `tests/test_study2_analysis.py`); not touched by A04.

  These are not actions Claude Code may take on its own.
- **Decisions already made by the researcher:** repository `Nick-is-building/AI-collusion-project`, private until submission, must be public at submission (plan §11, milestone 6); blind check no longer required (D10); Claude Code may commit and push (see `CLAUDE.md`, Git rules).

## Adding or splitting blocks

Choose a meaningful topic or development stage, not an arbitrary token or line count. Existing entries remain intact and retain their dates. Add a link from the index and any cross-references necessary to follow causal decisions across files. Do not create a second shortened "current history" as a replacement for these complete logs.
