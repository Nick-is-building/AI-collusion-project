# DEVLOG index — topic map, not a history summary

**Purpose:** Find the complete records needed for a Claude Code session without repeatedly loading unrelated DEVLOG blocks. No information is intentionally discarded. Do not use this index as evidence that a task was completed.

**Initial state:** Starter structure only. No Claude Code work is logged in these blocks yet. `PROJECT_PLAN.md` is version 2.5 (final for implementation, frozen; changes only as documented amendments). The researcher's own setup steps are recorded in `devlog/01_foundation.md`. `PROJECT_PLAN.md` documents earlier design discussions and reanalysis, but the files, checks, and outcomes it describes must be inspected/reproduced before being represented as independently confirmed here. Nothing in this index authorizes a run.

## Where to look

| Block | Topic / when to read | Current status |
|---|---|---|
| [`devlog/01_foundation.md`](devlog/01_foundation.md) | Repository setup, dependencies, upstream pinning, pre-sprint artifact intake and provenance, baseline verification, shared infrastructure | A01 tasks 0–2 done (prereg-v0, env, data provenance, Study 0 reproduced); A02 LICENSE check |
| [`devlog/02_pilot.md`](devlog/02_pilot.md) | Technical pilots, cost/timing measurements, feasibility checks, problems, go/no-go recommendations | A02: live P1, P2, P3, P9 (0.57 USD). A03: R0 mismatch cause found (task 1); P5, P11, P10 (task 4) |
| [`devlog/03_core_experiment.md`](devlog/03_core_experiment.md) | Study 1: context reconstruction, bait generation, replay, controls, fidelity, R1-live, model comparison | A01 tasks 3–7; A02 D2–D4; A03: D6/D7 baits (109 main), blind-check package (tablet), R5, R6, N1/N4, job lists, parallel runner |
| [`devlog/04_hysteresis.md`](devlog/04_hysteresis.md) | Study 2: branching trajectories, channel changes, partner intervention, run validity, persistence analyses | Not started |
| [`devlog/05_analysis_submission.md`](devlog/05_analysis_submission.md) | Statistical implementation, result validation, figures, paper, reproducibility and submission checks | A03: analysis code + simulation tests, PREREGISTRATION.md draft (untagged) |

## Reading and linking rules

1. On session entry, read this index and the complete `PROJECT_PLAN.md`, then the relevant DEVLOG block(s) **in full**. Read necessary older blocks when they contain dependencies, design decisions, or prior failures. Do not treat "not active" as "irrelevant" when the assignment depends on it.
2. Append new records to the **primary topic block**, never to this index. For work spanning blocks, add explicit links and entry headings rather than copying the same long record everywhere.
3. Update the table's *Current status* conservatively when work actually begins/completes. Status is for navigation only; verify details in the referenced entries and repository.
4. Claude Code may add new blocks, folders, or subtopics on its own if the structure warrants it. Update this index immediately, with clear labels and links; preserve existing history.
5. Keep an **Active work and cross-references** section updated with pointers, not compressed narratives. Remove stale pointers when tasks finish, but leave all historical log entries intact.

## Active work and cross-references

- **Assigned work:** A03 (`assignments/A03_bait_fixes_build_pilot.md`): tasks 1–3 done; task 4 (P5, P11, P10 live) and task 5 (report) follow. A02 and A01 done.
- **Active blocks:**
  - `devlog/02_pilot.md`: A03 task-1 entry (R0 bisection) and the pilot entries;
  - `devlog/03_core_experiment.md`: A03 task-2 entry (baits, blind check) and task-3 entry (R5, R6, jobs, parallel runner);
  - `devlog/05_analysis_submission.md`: A03 analysis entry.
- **Deviations:** `docs/deviations.md` D1–D12 (D6–D10 from A03; D7 corrected and D11–D12 decided by Nick in the A03 session). All were made before any bait was run.
- **Preregistration:** `PREREGISTRATION.md` (draft, **not tagged**); materials in `data/derived/prereg/` (`make_prereg_files.py` regenerates them; rerun before tagging).
- **Raw run evidence:** `results/raw/*.jsonl` (committed); countTokens log `results/token_counts/counts.jsonl` (committed); request payloads in `results/requests/` (local, hashed); launch logs in `logs/` (local).
- **Blind check:** `blind_check/` (INSTRUCTIONS.md, ANSWERS.md, 20 pair files, key hash); key `blind_check/key.local.json` local only. Optional per D10.
- **Code map:**
  - `src/replay/`: traces, variants (R0, CUT, R2, R3, R4, R4n), r5, r6, request, token_count, item_tables, dry_run, bait_common, baits_extraction, baits_data_search, build_baits.
  - `src/runner/`: runner, costs, estimates, item_lists, jobs, parallel; pilot scripts in `scripts/pilot/` (P1–P3, P5, P9–P11).
  - `src/analysis/`: stats, primary, fidelity, meta, simulate; `scripts/analysis/run_study1.py`.
  - Also `scripts/a03/` (bisection), `scripts/prereg/`, `src/reanalysis/`, `src/blind_check/`.
  - Derived tables in `data/derived/`; local scratch in `scratch/` (git-ignored).
- **Relevant dependencies:** `PROJECT_PLAN.md` (complete approved design as supplied; do not silently modify); initial technical setup and all claims of reproduced prior work belong in `01_foundation.md` once actually checked.
- **Pending decisions for Nick:**
  - level-1 fidelity reporting (the raw 95% rule is expected to fail; explained share as a diagnostic);
  - rep018_e02 D4 alternative (at most +1 item);
  - main-run stage cap and launch approval;
  - prereg-v1 tag;
  - R1-live driver (build step 6).

  These are not actions Claude Code may take on its own.
- **Decisions already made by the researcher:** repository `Nick-is-building/AI-collusion-project`, private until submission, must be public at submission (plan §11, milestone 6); blind check no longer required (D10); Claude Code may commit and push (see `CLAUDE.md`, Git rules).

## Adding or splitting blocks

Choose a meaningful topic or development stage, not an arbitrary token or line count. Existing entries remain intact and retain their dates. Add a link from the index and any cross-references necessary to follow causal decisions across files. Do not create a second shortened "current history" as a replacement for these complete logs.
