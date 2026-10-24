# DEVLOG 03 — Core experiment (Study 1)

## Scope

Context-gap replay builder, source trace reconstruction, bait generation and validation, replay variants, live continuation, model replication, fidelity testing, run outputs, analysis integration, and unexpected behavior. Refer to `PROJECT_PLAN.md` §§4, 8, 10, 13 for binding methodology.

## Initial state — starter file, not a work entry

No Study 1 implementation or experimental result is attested by this DEVLOG. Planned tasks and predictions in `PROJECT_PLAN.md` are not observed outcomes.

## Entries (append chronologically below)

<!-- Use the entry format in ../CLAUDE.md. Do not overwrite past entries. -->

## 2026-10-24 05:39–05:41 UTC — Claude Code (Opus 5.5), session A01 — Task 3: item tables (before any bait or replay output)

**Assignment / authorization:** A01 task 3. No API calls. No bait or replay output existed when the tables were built and committed.
**Built or changed:**
- `src/replay/item_tables.py`: builds the tables. Its module docstring is the authoritative procedure.
- `data/derived/items/candidates.csv` (168 rows; `set` = `main`/`pilot_holdout`; column `correct_counterpart` = JSON `{"R1":"R0p","R2":"R2","R3":"R3","R4":"R4","R4n":"R4n","R5":"R5","R6":"R6"}`).
- `data/derived/items/natural_error_set.csv` (35 rows).
- `data/derived/items/fidelity_set.csv` (63 rows).
- `tests/test_item_tables.py`.
**Decisions (algorithm choices where the plan does not fix one; not scientific changes):**
- Seed 2026, `numpy.random.default_rng(2026)`, numpy 2.5.4. The draw order is fixed: hold-out extraction (8), hold-out data search (12), then the fidelity matches in REJECT order.
- Candidates are sorted by (trace, ep_index). `item_id = repNNN_eEE_alice` (EE = evaluation episode).
- Hold-out: `rng.choice(..., replace=False)` per task type.
- Main list: the remaining 148 (61 extraction / 87 data search). This equals the plan's cap of 148, so the plan's random-drop rule (§8.1) is not triggered.
- Natural-error set: all 35 frame rows with Bob's task incorrect. `error_type` for extraction is computed from the evaluator's `missing_references` and `extra_references`.
- Fidelity set:
  - All 21 original REJECTs (all judges, all episodes).
  - For each REJECT, 2 matched ACCEPTs with the same task type and the same evaluation episode, no reuse.
  - Preference order: same trajectory first (that can only be the other judge in the same episode), then `rng.choice` among other trajectories.
  - Nearest-episode fallback defined but **not used**.
  - The plan does not mention peer correctness in the matching, so matching ignores it (recorded in the `peer_correct` column).
- R6: counterpart per §8.4 is R6 on the correct version. The separate comparison "R6 false rejections vs R0′" (§8.4) is an analysis contrast, not a counterpart.
**Checks performed:**
- `python -m src.replay.item_tables`. Hold-out spans 19 trajectories. Fidelity match levels: 17 same trajectory and episode, 25 same episode, 0 fallback.
- Second run gives identical SHA-256 (deterministic):
  - candidates.csv `353e5db6…9ca9c5`
  - fidelity_set.csv `897b7479…04c1`
  - natural_error_set.csv `06425765…cc22`
- `pytest`: 65 passed.
**Did not work:** none observed.
**State / limitations:**
- One candidate (main or hold-out) has an original REJECT verdict (167 accept / 1 reject among 168). It is also in the fidelity set as an original REJECT. Overlap between sets is allowed by the plan.
- Bait validity may reduce the main list later; the item flow is reported in task 6.
**Next:** Task 4 replay builder.
**Cross-references:** plan §§8.1, 8.4, 8.7; `devlog/01_foundation.md` task-2 entry (frame definition). Correction: that entry's header end time "06:20 UTC" is wrong; the commit was at 05:39 UTC.
