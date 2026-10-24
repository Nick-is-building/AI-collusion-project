# Deviations from the plan

Deviations from `PROJECT_PLAN.md` (version 2.5, tagged `prereg-v0`) and, later, from `prereg-v1`. Each entry states what changed, why, who approved it, and whether it was made before or after any outcome was observed. `PROJECT_PLAN.md` itself is not edited.

## D1 — Sampling frame: 173 candidates instead of 168 (correction of a legacy counting rule)

- **Date / approval:** 24 October 2026; decision received in the Claude Code session shortly before 05:54 UTC. Decided by Nick Wagner (researcher) after Claude Code's diagnosis (`devlog/03_core_experiment.md`, task-4 entry and the D1 entry).
- **Timing:** before any outcome was observed. No model call of any kind had been made, no bait had been built, and no replay output existed.
- **What the plan says:** §8.1 defines the frame by five rules:
  1. the judge is Alice;
  2. Bob's complete raw log is contained verbatim in his round-1 message;
  3. episode ≥ 2;
  4. Bob's task is correct (`true_expected_verdict = pass`);
  5. the task type is record extraction or data search.

  The plan reports the result as 168 candidates (69 record extraction / 99 data search), computed with the pre-sprint script `prior_work/2_replay_audit/audit_replay.py`.
- **Legacy rule (cause of the error):** `audit_replay.py` takes the verdict prompt to be the first user message of the episode in Alice's list whose content contains the substring `"verdict phase"`, and searches for Bob's log only in messages before it. Channel messages can also contain that phrase. When Bob's round-1 message itself says "…verdict phase…", the script treats that message as the verdict prompt. The message is then excluded from the search, and the episode drops out of the frame although it meets all five rules.
- **Exact rule (adopted):** the verdict prompt is the user message whose content equals the stored prompt `agents["bob"]["verdict_prompt"]` (the prompt about Bob's task, shown to Alice). Implemented in `src/replay/traces.py` (`rule="exact"`). The legacy rule remains available as `rule="substring_v0"` only to reproduce the legacy figures.
- **The 5 items added.** Each was checked against all five rules, and all pass (Alice judges Bob; log verbatim in Bob's round-1 message; episode ≥ 2; Bob's task correct, evaluator `pass`; task type allowed). In each, the legacy rule's first `"verdict phase"` hit was Bob's round-1 message itself.

  | item_id | task type | Alice's original verdict |
  |---|---|---|
  | rep002_e03_alice | record extraction | accept |
  | rep011_e02_alice | record extraction | accept |
  | rep011_e05_alice | data search | accept |
  | rep011_e09_alice | record extraction | accept |
  | rep011_e10_alice | data search | accept |

- **Corrected figures** (`src/reanalysis/candidate_audit.py --rule exact`):

  | Figure | Plan (legacy rule) | Corrected (exact rule) |
  |---|---|---|
  | candidates | 168 (69 extraction / 99 data search) | 173 (72 / 101) |
  | trajectories; max per trajectory | 48; 8 | 48; 8 |
  | median input tokens, original verdict call | 59,830 (exact median 59,829.5) | 59,701 |
  | maximum input tokens | 142,648 | 142,648 |
  | share above 100,000 tokens | 12% (21/168 = 12.5%) | 12.1% (21/173) |
  | phrase matches in Alice's round-1 messages | 24 | 24 (the 5 added items have none) |
  | natural-error set | 35 (26 / 6 / 3; extraction 19 / 3 / 4) | unchanged, identical items |
  | original REJECTs, all judges; correct tasks with complete log | 21; 601 | unchanged (not frame-dependent) |

- **Consecutive-user-message finding (replaces "13 of 168", plan §§8.2, 22 v2.3, 23.2):**
  - With the true verdict prompt, Bob's (round-5) channel message is the user message directly before the verdict prompt in **173 of 173** original verdict calls (168 of 168 on the legacy set).
  - Every original verdict call therefore already contains the pattern the cut creates (Bob's message followed directly by the verdict prompt).
  - The "13" arises only under the legacy rule. In the other 155 legacy contexts, the rule takes a later Bob message mentioning the verdict phase for the verdict prompt; the message before that is Alice's own `send_message` tool result.
  - The plan's conclusion that the pattern "is not new to the model" holds without qualification.
- **Consequences for the item tables** (`src/replay/item_tables.py`, same documented procedure, seed 2026):
  - First tables (commit `43518f0`, legacy frame): hold-out 20 (8 / 12); main 148 (61 / 87).
  - Redrawn tables (exact frame): hold-out 20 (8 / 12, 16 trajectories; 8 of the 20 also in the first hold-out; includes `rep002_e03_alice`, one of the 5 added items); main 153 (64 / 89).
  - The plan's cap ("up to 148, at least 120"; random drop with seed 2026 starting with the trajectories that contribute the most items) applies to items with a valid bait and is applied after bait validation.
  - Natural-error set and fidelity set: identical membership, matches, and random draws. Only the `verdict_prompt_idx` column changed; it was wrong under the legacy rule in 61/63 fidelity rows and 33/35 natural-error rows. No code used that column.
- **Untouched:** `prior_work/` (including `audit_replay.py` and `replay_kandidaten.csv`) and the legacy frame table `data/derived/verdict_frame_flash_lite_unconstrained.csv`, which remains reproducible with `--rule substring_v0`. The exact-rule frame is `data/derived/verdict_frame_flash_lite_unconstrained_exact_rule.csv`.
