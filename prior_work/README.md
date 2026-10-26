# Prior work (created before or at the start of the sprint)

This folder holds the files Nick Wagner prepared before the project's sprint work began. The original files are kept unchanged, with their original German names, so that the checksums in `1_reanalyse/pruefsummen_reanalyse.txt` and the evidence archive remain valid. `INHALT.md` is the original German table of contents; this file is its English description. All times are UTC. According to the sprint page, the AI Collusion Research Sprint program began on 23 October 2026 at 15:15 UTC at the earliest.

## `1_reanalyse/`: reanalysis of Shi et al.'s verdicts (before the sprint, 23 Oct 2026, 12:43–13:36 UTC)

| File | Content |
|---|---|
| `reanalyse_shi.py` | Reanalysis of Shi et al.'s published trajectories (strict log transmission, discrimination between correct and incorrect peer tasks) |
| `urteile_reanalyse.csv` | 4,000 verdicts from 4 conditions |
| `trennschaerfe_alle_bedingungen.csv` | Discrimination for all 53 conditions |
| `pruefsummen_reanalyse.txt` | Dataset revision (SALT-NLP/agent-collusion `2eba8f3`), upstream code commit (`5afb2c5`), SHA-256 of the script, inputs and verdict table |
| `nachweispaket_reanalyse.zip` | Complete evidence package (check script `pruefe_alles.py`, all data, checksums); recomputed independently with ChatGPT, all checks passed |

In the project this is Study 0. It was reproduced in assignment A01 (`devlog/01_foundation.md`).

## `2_replay_audit/`: audit of replay candidates (23 Oct 2026, 15:37 UTC, after the earliest program start)

| File | Content |
|---|---|
| `audit_replay.py` | Audit of the replay candidates in the 50 published traces (no API calls) |
| `replay_kandidaten.csv` | All candidates with verifier, round, episode, task type and correctness |

## Project plan

`INHALT.md` also lists the project plan (`3_plan`). It is not stored in this folder: the plan, version 2.5, was drafted before the sprint and frozen, and lives at the repository root as `PROJECT_PLAN.md`. Changes after freezing are recorded as deviations in `docs/deviations.md`.

## Boundary

The reanalysis predates the sprint; the replay-candidate audit ran after the earliest program start. Everything from the pilot onward (`devlog/02_pilot.md` and later) is sprint work.
