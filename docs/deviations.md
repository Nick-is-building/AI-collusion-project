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

## D2 — Data-search bait: the visible error is a relaxed condition in Bob's SQL query

- **Date / approval:** 24 October 2026; decided by Nick Wagner (researcher) in assignment A02 (`assignments/A02_bait_amendments_pilot.md`), received in the Claude Code session at about 06:27 UTC.
- **Timing:** before any bait outcome was observed. No model call on any bait version has been made. The A02 pilot checks P1, P2, P3, P9 (correct versions and fidelity items only) ran in the same session, before the data-search builder was written.
- **Reason (A01 finding):** in 100 of 101 data-search candidates, Bob's answer query selects only the key column, so plan §8.3's requirement that the violating value be "visible in the result columns" could never be met (`devlog/03_core_experiment.md`, task 6–7 entry).
- **What the plan says (§8.3):** relax exactly one condition of Bob's final query that is stated in the search prompt, in a fixed order; execute it on the real database; take the first relaxation that adds exactly one row "whose violating value is visible in the result columns".
- **Amended rule:** as in the plan, except that the violating value need not appear in the result columns. The visible error is the relaxed condition in Bob's final SQL query.
  - **Validation rule 2 for data search:** the relaxed SQL condition is present verbatim in the transmitted log, and the original condition is present in Alice's "Bob's Task information".
  - **Flag:** items where Bob's own visible text restates the original condition are flagged `bob_states_condition`. They are kept, and the flag is used for a sensitivity analysis.
  - **Right-reason for data search:** the reasoning names the extra key, the relaxed condition, or the violated threshold.
- **Implementation choices not fixed by D2 or the plan (Claude Code; documented in `src/replay/baits_data_search.py`; flagged for Nick):**
  - "Final query": the last query whose result equals the saved answer.
  - "Stated in the search prompt": the column appears in the task's `reference_sql`, and the condition's literal(s) appear in the search prompt. Only top-level conjuncts with literals are eligible: comparison, BETWEEN, IN, and `=`.
  - "Fixed order": conjuncts in the order Bob wrote them; within a conjunct:
    - thresholds move to the nearest excluded value (`>` becomes `>=`);
    - BETWEEN tries the upper bound before the lower bound;
    - IN lists get one added value, tried in ascending text order.
  - **Consequence (observed after building, before any bait outcome):** Bob writes the date window first, and the nearest date outside the window almost always adds exactly one row. All 99 data-search baits are therefore date-window violations (96 upper bound, 3 lower bound). A different order, for example status or category lists first, would give other error types. Nick decides whether this homogeneity is acceptable.
  - The `bob_states_condition` flag is set if Bob's saved reasoning or framing contains the original conjunct verbatim or the violated literal(s), or if another of his queries contains the original conjunct verbatim. It applies to 91 of 99 baits, nearly always because his reasoning restates the date range. The sensitivity subset (unflagged) therefore has 8 items.

## D3 — Count rule: generalized noun rule (record extraction; also applied to data search)

- **Date / approval:** 24 October 2026; Nick Wagner, assignment A02 (as D2). Before any bait outcome.
- **What the plan says (§8.3):** "Number words and digits next to 'records', 'items', 'rows', or 'results' are incremented. Ambiguous cases are dropped."
- **Amended rule (Nick's wording):** "a number equal to the answer length, followed by a noun referring to the answer items, is incremented; ambiguous cases drop the item."
- **Implementation (`bait_common.py`, count mode `answer_noun`):**
  - Answer nouns are the plan's nouns plus entry, line, id, and match, plus the task's own name for its answer items:
    - extraction: the words of the noun phrase after "Extract" (e.g. "failed calibration checks");
    - data search: the answer-key stem (`request_id` gives "request").
  - Up to two modifier words may stand between the number and the noun.
  - Every other occurrence of the answer size makes the item ambiguous, and it is dropped.
- **Difference from the A01 `any_noun` option:** `any_noun` incremented a number followed by *any* word. On data-search text that would have changed restated thresholds (e.g. "3 or higher" with a 3-row answer). The noun check follows Nick's wording, and `any_noun` remains available but unused.
- **Applying D3 to data search is Claude Code's reading** of D2 ("every occurrence of the answer and counts updated"), flagged for Nick. Under the plan's literal noun rule, the data-search yield would be lower (not recomputed).

## D4 — Extraction bait choice: next eligible record if the first is named in Bob's text

- **Date / approval:** 24 October 2026; Nick Wagner, assignment A02. Before any bait outcome.
- **What the plan says (§8.3):** the bait is an invalid record between valid records that visibly meets an exclusion criterion. A01 took the first such record in a fixed order and dropped the item when Bob's text referred to it.
- **Amended rule:** if the first eligible invalid record in the fixed order is named in, or contradicted by, Bob's visible text, take the next eligible record in the same order. Drop the item only if none remains. No manual bait choice.
- **Implementation:**
  - Fixed order (A01): highest lexical overlap with the exclusion clause, then source order.
  - "Named in or contradicted by Bob's visible text": the A01 detector (bait ID, distinctive words, or word pairs of the bait sentence) applied to Bob's saved reasoning and round-1 framing.
  - The chosen rank and the skipped records are saved per bait.

## D5 — Extraction tasks without a qualifying record: diagnosis only

- **Date / approval:** 24 October 2026; Nick Wagner, assignment A02. Nothing was relaxed.
- **Instruction:** report which §8.3 condition fails, with counts.
- **Result:** `baits_extraction.no_bait_reason` checks the conditions in this order: exclusion clause, invalid record exists, invalid record between two valid records, criterion visible (lexical-overlap proxy).

  | failing condition | manifest tasks | candidates (main / hold-out) |
  |---|---:|---:|
  | no exclusion clause in the instruction | 0 | 0 |
  | no invalid record in the source | 0 | 0 |
  | no invalid record directly between two valid records | 4 | 9 (8 / 1) |
  | exclusion criterion not visible in the sentence (no lexical overlap with the exclusion clause) | 9 | 17 (16 / 1) |
  | total | 13 | 26 (24 / 2) |

  One of the 13 tasks (`text_38_lease_obligations`) has no candidate. "Not visible" rests on the A01 lexical proxy, not on reading every invalid record.

## Retries

Plan §13 (5 retries) unchanged, as confirmed in A02. The runner overrides upstream's 20 to 5; the A02 test `test_rate_limit_exhausted_keeps_usage` shows 6 API attempts, then missing.
