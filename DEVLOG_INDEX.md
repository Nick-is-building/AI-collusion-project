# DEVLOG index — topic map, not a history summary

**Purpose:** Find the complete records needed for a Claude Code session without repeatedly loading unrelated DEVLOG blocks. No information is intentionally discarded. Do not use this index as evidence that a task was completed.

**Initial state:** Starter structure only. No Claude Code work is logged in these blocks yet. `PROJECT_PLAN.md` is version 2.5 (final for implementation, frozen; changes only as documented amendments). The researcher's own setup steps are recorded in `devlog/01_foundation.md`. `PROJECT_PLAN.md` documents earlier design discussions and reanalysis, but the files, checks, and outcomes it describes must be inspected/reproduced before being represented as independently confirmed here. Nothing in this index authorizes a run.

## Where to look

| Block | Topic / when to read | Current status |
|---|---|---|
| [`devlog/01_foundation.md`](devlog/01_foundation.md) | Repository setup, dependencies, upstream pinning, pre-sprint artifact intake and provenance, baseline verification, shared infrastructure | Not started in this DEVLOG |
| [`devlog/02_pilot.md`](devlog/02_pilot.md) | Technical pilots, cost/timing measurements, feasibility checks, problems, go/no-go recommendations | Not started |
| [`devlog/03_core_experiment.md`](devlog/03_core_experiment.md) | Study 1: context reconstruction, bait generation, replay, controls, fidelity, R1-live, model comparison | Not started |
| [`devlog/04_hysteresis.md`](devlog/04_hysteresis.md) | Study 2: branching trajectories, channel changes, partner intervention, run validity, persistence analyses | Not started |
| [`devlog/05_analysis_submission.md`](devlog/05_analysis_submission.md) | Statistical implementation, result validation, figures, paper, reproducibility and submission checks | Not started |

## Reading and linking rules

1. On session entry, read this index and the complete `PROJECT_PLAN.md`, then the relevant DEVLOG block(s) **in full**. Read necessary older blocks when they contain dependencies, design decisions, or prior failures. Do not treat "not active" as "irrelevant" when the assignment depends on it.
2. Append new records to the **primary topic block**, never to this index. For work spanning blocks, add explicit links and entry headings rather than copying the same long record everywhere.
3. Update the table's *Current status* conservatively when work actually begins/completes. Status is for navigation only; verify details in the referenced entries and repository.
4. Claude Code may add new blocks, folders, or subtopics on its own if the structure warrants it. Update this index immediately, with clear labels and links; preserve existing history.
5. Keep an **Active work and cross-references** section updated with pointers, not compressed narratives. Remove stale pointers when tasks finish, but leave all historical log entries intact.

## Active work and cross-references

- **Assigned work:** None recorded yet. The user controls assignments and approvals.
- **Active blocks:** None yet.
- **Relevant dependencies:** `PROJECT_PLAN.md` (complete approved design as supplied; do not silently modify); initial technical setup and all claims of reproduced prior work belong in `01_foundation.md` once actually checked.
- **Pending decisions:** Refer to `PROJECT_PLAN.md` §18. These are open decisions listed by the plan, not actions Claude Code may take on its own.
- **Decisions already made by the researcher:** repository `Nick-is-building/AI-collusion-project`, private until submission, must be public at submission (plan §11, milestone 6); blind bait check by Nick (plan §8.3, §18.4); Claude Code may commit and push (see `CLAUDE.md`, Git rules).

## Adding or splitting blocks

Choose a meaningful topic or development stage, not an arbitrary token or line count. Existing entries remain intact and retain their dates. Add a link from the index and any cross-references necessary to follow causal decisions across files. Do not create a second shortened "current history" as a replacement for these complete logs.
