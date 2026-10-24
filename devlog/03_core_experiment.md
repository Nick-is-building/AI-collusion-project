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

## 2026-10-24 05:41–06:05 UTC — Claude Code (Opus 5.5), session A01 — Task 4: replay builder, cut, edited histories, dry run; frame finding (173 vs 168)

**Assignment / authorization:** A01 task 4 (build-order step 1). No API calls. A read-only subagent read the upstream files of plan §23.1; its findings are in `devlog/01_foundation.md` (task-2 entry, "Upstream reading"). I re-read the critical code myself: `agents.run_agent_turn`, `_complete_with_retries`, `_select_tools_and_choice`; `episode_runner._run_agent_attempts`, `_run_verdict_phase`, `_record_forced_verdict`; `memory/messages.py`; `protocol/state.py`; `protocol/submissions._submit_verdict`.
**What I learned that affects the build:**
- Stored message lists are cumulative per episode and contain no internal markers. The test confirms `results[e-1]` is an exact prefix of `results[e]` for all 50 traces and both agents.
- No upstream function returns completion kwargs without calling the API. The only call site is `completion(...)` inside `agents._complete_with_retries`, with the messages transformed by `model_visible_messages` → `with_prose_split_from_tool_calls` → `with_prompt_cache_breakpoint`. For this model, the last two are no-ops (subagent; consistent with the observed identity of sent and built messages).
- `agents[X]["verdict_prompt"]` is the prompt *about X's task*, shown to X's peer.
- **LiteLLM network side effect:** on import, LiteLLM fetches its cost map from GitHub unless `LITELLM_LOCAL_MODEL_COST_MAP=True`. `src/upstream.py` sets that variable.
**Built or changed:**
- `src/upstream.py`: puts the submodule on `sys.path` and selects LiteLLM's offline cost map.
- `src/replay/variants.py`: builds R0, CUT (R0′/R1 base), R2, R3, R4, R4n. A `bob_r1_content` override is used for bait versions; it replaces the only place in Alice's verdict-time context that carries Bob's answer. The R4n system prompt is the fixed text from plan §8.4.
  - R2 uses upstream's "No memory" mechanism: boundary markers at the known episode starts, then `limit_episode_blocks(m, 0)` and `model_visible_messages`.
  - R3 is custom (no upstream helper exists). For each earlier episode it removes the communication opening up to, but not including, that episode's verdict prompt.
  - Not built: R5 (needs the token-counting endpoint, which A01 forbids, and a Gutenberg filler text, whose download source A01 does not authorize) and R6 (build-order step 4).
- `src/replay/request.py`: `run_verdict()` drives upstream `episode_runner._run_agent_attempts`, which brings the 3 verdict attempts, forced `submit_verdict`, upstream retries, `_submit_verdict`, and `_record_forced_verdict`. The single seam is `experiments.agents.completion`, wrapped by a recorder that captures the exact kwargs.
  - Also provides `mock_backend()` (a LiteLLM `ModelResponse`, no network), `request_hash` (SHA-256 of canonical JSON of the full kwargs), and `messages_hash`.
- `src/replay/dry_run.py` writes `data/derived/dryrun_request_hashes.csv`: 1,101 mock requests = 173 candidates × {R0, CUT, R2, R3, R4, R4n} + 63 fidelity R0.
- `src/replay/traces.py`: verdict prompt now identified by exact equality with `agents[peer]["verdict_prompt"]` (`rule="exact"`). The old rule is kept as `rule="substring_v0"`.
- `src/reanalysis/candidate_audit.py`: `--rule` option. `src/replay/item_tables.py`: `FRAME_RULE = "substring_v0"`, so the committed tables stay reproducible.
- `data/derived/verdict_frame_flash_lite_unconstrained_exact_rule.csv`: new, 208 rows. The committed `verdict_frame_flash_lite_unconstrained.csv` is unchanged and reproduced by `--rule substring_v0` (`cmp` identical).
- `tests/test_replay_contexts.py`: 11 tests.
**FINDING: sample frame is 173, not 168 (decision needed from Nick; not decided here).**
- Cause: the pre-sprint `audit_replay.py` (and my first `traces.py`, which copied it) takes the first user message of the episode containing "verdict phase" as the verdict prompt.
- In 5 episodes, Bob's round-1 message itself contains that phrase, so the rule treats Bob's log message as the verdict prompt and excludes it from the search: rep002 ep3 (extraction), rep011 ep2 (extraction), rep011 ep5 (data search), rep011 ep9 (extraction), rep011 ep10 (data search).
- Plan §8.1's rule, implemented literally with the exact verdict prompt, gives **173 candidates (72 extraction / 101 data search)**, 48 trajectories, max 8 per trajectory, and a median verdict-call input of 59,701 tokens (max 142,648; 21/173 = 12.1% above 100k). The 168 are a strict subset. The natural-error set (35) is identical under both rules. Phrase matches: 24 under both rules.
- Consequences if 173 is adopted: the main list would be 153 > the cap of 148 (§8.1 random-drop rule, seed 2026, "starting with the trajectories that contribute the most items"), or the hold-out would be redrawn. These are Nick's choices.
- Current state: the committed item tables (168) are unchanged. Everything downstream is built for the 173 superset, so either decision works.
- **Warning:** the `verdict_prompt_idx` columns in `items/candidates.csv` and `items/fidelity_set.csv` come from the substring rule and are wrong for 155/168 candidates. No code uses them; `variants.load_item` determines the verdict prompt by the exact rule (tested).
**FINDING: "consecutive user messages in 13 of 168" (plan §§8.2, 22, 23.2) is an artifact of the same rule.**
- With the true verdict prompt, Bob's (round-5) message directly precedes it in **168/168** originals (173/173).
- The "13" is reproduced only with the substring rule; the test asserts both.
- The plan's conclusion (the pattern "is not new to the model") holds more strongly than stated: the pattern occurs in every original verdict call. Recorded for the plan's deviation list; Nick decides any wording.
**Offline observation (not a pilot result):** LiteLLM 1.94.1's local Gemini conversion (`_gemini_convert_messages_with_history`) merges consecutive user messages into one `user` content with several parts. For CUT, Bob's message and the verdict prompt become 2 parts of one turn, as in the originals; for R4, 3 user messages become 1 content with 3 parts. Whether the API processes the requests identically is still open for P2/P3.
**Checks performed:**
- `pytest`: 76 passed. Covered:
  - cumulative-prefix property;
  - R0 byte-identical (canonical JSON) with all signature carriers (tool-call IDs with `__thought__`, `provider_specific_fields`) for 168 candidates + 63 fidelity cases;
  - CUT prefix identical, Bob's round-1 message starts `[round=1/5][from=bob]`, no round instruction after the cut;
  - Bob-before-verdict pattern (168/168 exact, 13/168 substring);
  - verdict prompt equals the stored prompt;
  - R2 equals the manual slice;
  - R3 removes only earlier communication;
  - R4/R4n structure;
  - bait override changes exactly one message;
  - upstream request path sends the built messages with `model=gemini/gemini-3.1-flash-lite`, temperature 1.0, max_tokens 64000, reasoning_effort high, `tool_choice` forced `submit_verdict`, tools = [submit_verdict];
  - attempt loop: 3 failed attempts → forced reject; 1 failure → second attempt.
- Dry run: 1,101 requests; CSV SHA-256 `088180ac…4a42`, identical on a second run. 10 duplicate request hashes, all the same item appearing in both the candidate and fidelity sources (expected).
**Did not work:** First version of `variants.load_item` counted the system prompt as part of episode 0; fixed (episode 0 starts at index 1) before any test ran. The first test run failed on the "13 of 168" assertion, which exposed the frame finding above.
**State / limitations:**
- The tool schemas of the original requests are not stored in the traces; equality of the `submit_verdict` schema with the original can only be confirmed by P2 `input_tokens` identity.
- The dataset was produced by a code revision or post-processing not identical to `5afb2c5` (field names; see `devlog/01_foundation.md`), so P2 is the real test of request identity.
**Next:** Task 5 (pilot harness).
**Cross-references:** plan §§8.1, 8.2, 8.4, 23.1, 23.2; `devlog/01_foundation.md` (task-2 entry; its "13 of 168" reading is superseded by this entry).

## 2026-10-24 05:50–05:56 UTC — Claude Code (Opus 5.5), session A01 — D1: frame corrected to 173 (Nick's decision); item tables redrawn

**Assignment / authorization:** Nick's decision, relayed into the session at about 05:52 UTC: once the diagnosis confirms that the 5 additional candidates meet all five rules of plan §8.1, use the exact-rule frame (173) for everything downstream. The preregistered definition is the §8.1 rules. Document in `docs/deviations.md` as a correction made before any outcome was observed. Redraw item tables already drawn from the 168 with the same procedure and seed. Keep the legacy CSV and `prior_work/` untouched. Stop if any of the 5 fails a criterion. Use an in-repo git-ignored scratch folder instead of `/tmp`.
**Built or changed:**
- `docs/deviations.md`: new; entry D1.
- `src/replay/item_tables.py`: `FRAME_RULE = "exact"`; docstring updated (main list 153; the cap of 148 is applied after bait validation).
- `data/derived/items/*.csv`: regenerated.
- `tests/test_item_tables.py`, `tests/test_replay_contexts.py`: updated to 173.
- `.gitignore`: `scratch/`.
- `src/replay/traces.py`: docstring.
**Checks performed:**
- Each of the 5 items checked against all five §8.1 rules from the raw trace (Alice judges Bob; Bob's `get_log` raw log verbatim in his single `[round=1/5][from=bob]` message; evaluation episode ≥ 2; Bob `true_expected_verdict = pass` and evaluator `quality_verdict = pass`; task type extraction or data search). **All 5 pass.** For each, the legacy rule's first "verdict phase" hit is Bob's round-1 message.
- Item tables: same procedure, seed 2026.
  - Hold-out 8 extraction / 12 data search over 16 trajectories; 8 of 20 coincide with the first draw. `rep002_e03_alice` (one of the 5) is in the new hold-out.
  - Main 64 / 89 = 153.
  - Fidelity and natural-error sets: identical membership, matches, and draws; only the formerly wrong `verdict_prompt_idx` column changed (61/63 and 33/35 rows).
  - Rebuild deterministic: second run gives identical hashes. candidates.csv `84dc4c14…c7f1`, fidelity_set.csv `ce524a66…981a`, natural_error_set.csv `0638536e…4cc8`.
- `pytest`: 76 passed.
- Corrected figures are in `docs/deviations.md` (median 59,701 tokens, max 142,648, 21/173 = 12.1% > 100k; Bob's message directly before the verdict prompt 173/173).
**Did not work:** A string replacement for the `SEED` constant also hit the module docstring of `item_tables.py`. This was caught on inspection and fixed; the regenerated tables were unchanged (hash-checked).
**Scratch files:** `/tmp/h1`, `/tmp/frame_old.csv`, `/tmp/f_sub.csv` (written earlier in this session, outside the repository, contrary to CLAUDE.md) were moved into `scratch/` or deleted. The harness fork was told to use `scratch/` as well.
**State / limitations:** Everything downstream (dry run, baits, pilot item draws) uses the 173 frame. The dry-run hashes (task 4) were already computed on the 173.
**Next:** Bait builders (task 6), then the cap rule after validation.
**Cross-references:** `docs/deviations.md` D1; plan §§8.1, 8.2, 23.2; `devlog/01_foundation.md` task-2 entry (legacy figures reproduced there remain correct as reproductions of the legacy rule).

## 2026-10-24 06:05–06:15 UTC — Claude Code (Opus 5.5), session A01 — Tasks 6–7: baits (build-order step 2), blind-check generator; BLOCKED on bait yield

**Assignment / authorization:** A01 tasks 6 and 7. No API calls.
**Correction:** the task-5 entry in `devlog/02_pilot.md` gives its end time as "06:12"; the commit was at 06:04 UTC.
**Built or changed:**
- `src/replay/bait_common.py`: count rule (plan §8.3), `stray_counts`, diffs.
- `src/replay/baits_extraction.py`: extraction bait choice, edits, and validation rules 1–3 (docstring = authoritative procedure).
- `src/replay/build_baits.py`, which writes:
  - `data/derived/baits/<item_id>.json` (`bob_r1_content`, `bait_raw_log`, hashes, edits, evaluator result, validation);
  - `data/derived/baits/diffs/<item_id>.diff`;
  - `data/derived/baits/item_flow.csv` (every candidate with its drop reason; SHA-256 `0eb21e4b…faf6`).
- `src/replay/dry_run.py`: now also covers bait versions (R1, R2, R3, R4, R4n). 1,166 requests; CSV SHA-256 `cf1cfecf…92cf`.
- `src/blind_check/make_package.py`: task-7 generator. Seed 2026; per-pair Markdown with the task information and both raw logs as A/B; the answer form; key in the git-ignored `blind_check/key.local.json`, with only its SHA-256 committed. It refuses to run with fewer than N validated baits.
- Tests: `tests/test_baits_extraction.py` (16), `tests/test_blind_check.py` (2).
- `tests/test_runner.py`: fixed a test defect (see "Did not work").
**Extraction bait procedure and its decisions (implementation of §8.3; not decided by the plan, flagged for Nick):**
1. *Bait choice per task.* The bait is an invalid record lying directly between two valid records in source order (the plan's "sits between valid records"). It must share at least one content word (5-letter prefix) with the instruction's "Exclude …" clause that is not in the inclusion part. Highest overlap wins, then the earliest.
   - Without the direct-neighbour condition, generic background prose was chosen in 10 tasks; I rejected that variant after reading.
   - **I read all 37 chosen baits against their instructions; every one visibly meets an exclusion clause.** 13 tasks have no qualifying record.
2. *Edits.* Every `resolve_records` call (arguments and result) and every `save_final_answer` call get the bait inserted at its source-order position. The log is re-serialized with upstream `_format_private_raw_log`, and the answer keeps its original separator style. A complete answer list in Bob's framing gets the bait ID; counts are incremented.
3. *Drops as "ambiguous" (plan: "Ambiguous cases are dropped"), added after reading Bob's texts:*
   - **(a)** Bob's own reasoning or framing refers to the bait record, e.g. "I excluded … (sesame noodles icon)", "Export crash (fixed)", "excluded Leo (voluntary change)". The bait version would then contradict itself, so I treated it as an occurrence the plan's consistency rule must cover. Detection: bait ID, distinctive words or names of the bait sentence (absent from valid records and from the instruction's word prefixes), or distinctive word pairs. I read all remaining built baits: 13 survive, with no residual references.
   - **(b)** Bob's reasoning lists the answer IDs or enumerates the answer.
   - **(c)** The answer size appears outside the plan's count pattern, e.g. "identified 12 lines", "8 access removal cases", "eight cases". The plan's literal noun list (records/items/rows/results) would leave a visible count of n next to n + 1 IDs.
   - **(d)** An earlier save with an object-list answer.
4. *Count mode switch.* `plan_nouns` (default, the plan's literal rule) or `any_noun`, which also increments "n <noun>". **`any_noun` is not adopted; it is offered to Nick as an option.**
**Data-search baits: not buildable under §8.3.**
- In 100 of 101 data-search candidates, Bob's only, or final, answer query selects only the key column (e.g. `SELECT T.ticket_id …`).
- In the remaining one (rep013_e05, hold-out), the multi-column query is a single-ticket check, not the answer query.
- So no relaxation can add a row "whose violating value is visible in the result columns". Under the rule, all 101 are dropped.
- The plan's contingency for P4 failing is "use the remaining extraction items" (§§8.1, 10).
- Not built: an SQL relaxation builder, because it would produce zero items under the rule. The visible error could only live in the SQL text (the relaxed WHERE condition). That would be a different bait design and is Nick's decision.
**Item flow (plan §23.4; count mode `plan_nouns`):**

| | candidates | baits built | baits validated (rules 1–3) |
|---|---:|---:|---:|
| extraction, main | 64 | 11 | 11 |
| extraction, hold-out | 8 | 2 | 2 |
| data search, main | 89 | 0 | 0 |
| data search, hold-out | 12 | 0 | 0 |

- Extraction drop reasons (72 → 13):
  - no qualifying bait record: 26 (13 tasks)
  - Bob's reasoning refers to the bait record: 14 (plus 2 more caught after the name rule was fixed)
  - answer size outside the count rule: 14 in reasoning, 1 in framing
  - reasoning lists answer IDs: 1
  - object-list answer: 1
  - The exact counts per reason are in `item_flow.csv`.
- With `any_noun` (not adopted; measured before the name-rule fix): 25 validated (21 main / 4 hold-out). After the fix it would be slightly lower; not recomputed.
- **Consequences:**
  - The plan's target (§8.1: at least 120, up to 148) is unreachable. Even the extraction-only fallback assumed 61 items.
  - P11 has baits for 2 of its 20 hold-out items (`p11_effect_check --plan`: "baits missing for 18 of 20").
  - The blind check needs 20 pairs and only 13 validated baits exist, so task 7 is blocked. The generator ran and refused: "blocked: 13 validated baits, 20 pairs required". No package was produced, and no key exists.
**Checks performed:**
- `pytest`: 114 passed, including: every saved bait rebuilds byte-identically; rules 1–3 hold; Shi et al.'s evaluator scores the bait answer as `fail` with `extra_references == [bait_id]` and the original as `pass`; in every replay variant exactly one message differs; the bait choice sits between valid records; count-rule units; blind-check structure, label-leak check, and key hash in `scratch/`.
- One diff read by eye (rep023_e04, before it was dropped by rule 3a): the edits were in the right places.
**Did not work (all fixed, nothing left in an unknown state):**
- First bait choice (keyword overlap only) picked background prose.
- The separator style of the answer was not preserved; 5 items were wrongly dropped until fixed.
- My shell filter `grep -v warn` hid output lines that contained the word "warn"; stderr now goes to `scratch/stderr.txt`.
- The `any_noun` mode first double-counted "12 lab results"; fixed with a plan-rule precedence.
- The name rule skipped the sentence-initial word, so "Leo is on track…" was not caught (rep027_e07 was wrongly built); fixed, and re-verified by reading.
- The blind-check extraction sliced the log by framing offsets, which change under framing edits; fixed by saving `bait_raw_log`.
- `tests/test_runner.py::test_missing_verdicts` was flaky (about 1 in 3): it took the last "call" line across run files whose names can sort in either order within the same second. Fixed by selecting the line by `call_id` (`call_id("pilot")`); the assertions are unchanged. 8/8 consecutive passes afterwards.
**State / limitations:**
- The rules 3a–3c drops are my operationalization of "every occurrence … ambiguous cases are dropped". They are conservative and documented, but scientifically consequential; Nick decides.
- The bait choice relies on a lexical rule plus my reading; the blind check by Nick is still to come.
**Next (decisions for Nick, not started):**
1. Data-search bait design (SQL-visible relaxation or drop data search).
2. Extraction count mode (`plan_nouns` vs `any_noun`).
3. Whether to accept manually chosen baits for the 13 tasks without a lexical match.
4. How to proceed given the reduced sample (the plan's minimum is 120).
5. Blind check: with fewer than 20 baits, use all available, or wait.
**Cross-references:** plan §§8.1, 8.3, 10 (P4, P11), 11 (milestone 1), 23.2, 23.4; `devlog/02_pilot.md`.

## 2026-10-24 06:36–06:55 UTC — Claude Code (Opus 5.5), session A02 — D2–D4 bait builders, rebuild, item flow, D5, blind-check package

**Assignment / authorization:** `assignments/A02_bait_amendments_pilot.md`, tasks 2–4. Decisions D2–D5 are Nick's, recorded in `docs/deviations.md` with timing (before any bait outcome). No model call was made for this work.
**Built or changed:**
- `src/replay/baits_data_search.py` (new, D2). The docstring is the authoritative procedure. It covers:
  - the answer query;
  - eligible conjuncts: column in `reference_sql` and literal(s) in the prompt;
  - the fixed relaxation order;
  - execution on `task/data-search/dbs/ops_search.sqlite` with upstream `_connect_readonly_sqlite`/`_sqlite_rows` (the original answer-query result must be reproduced exactly first);
  - the edits, the `bob_states_condition` flag, rules 1–3, and the right-reason markers.
- `src/replay/bait_common.py`: count mode `answer_noun` (D3), `answer_nouns`, `extraction_head_phrase`, `forms`.
- `src/replay/baits_extraction.py`:
  - `eligible_baits` (fixed order), with `choose_bait` kept;
  - D4 selection in `build_bait`, saving `bait_rank` and `skipped_baits`;
  - `no_bait_reason` (D5);
  - default count mode `answer_noun`.
- `src/replay/build_baits.py`: both task types. The item flow gains the columns `no_bait_reason`, `bait_rank`, `bob_states_condition`, and `bob_states_condition_where`.
- `src/blind_check/make_package.py`: task types in proportion to the validated baits (largest remainder) and type-specific error text in the key.
- Tests:
  - `tests/test_baits_data_search.py` (new): every saved bait rebuilds byte-identically and passes rules 1–3; the original answer passes upstream's evaluator; the relaxed query reproduces the logged result on the database; the added row is not returned by the original query; the violated literal is in the prompt; only one message differs in every replay variant; plus unit tests for parsing, prompt literals, and the flag.
  - `tests/test_baits_extraction.py`: D3, D4, D5, and flow tests.
  - `tests/test_blind_check.py`: allocation test.
- Regenerated:
  - `data/derived/baits/` (123 JSON files + diffs; `item_flow.csv` SHA-256 `6f390ba0…0bea`);
  - `data/derived/dryrun_request_hashes.csv` (1,716 mock requests incl. 123 × 5 bait variants; SHA-256 `b1dfe204…b06`).
- `blind_check/` (new): `pairs/pair_01..20.md`, `answers_nick.md`, `key_sha256.txt`. The key `blind_check/key.local.json` is local and git-ignored.
**Decisions (implementation, not scientific; flagged in `docs/deviations.md`):**
- D2 fixed order = conjunct order in Bob's query, then thresholds to the nearest excluded value, BETWEEN upper before lower, IN values in ascending order.
- D3 noun check implemented from Nick's wording ("a noun referring to the answer items"), narrower than A01's `any_noun`.
  - A first version took all words of the task text as answer nouns. I rejected it before building because "3 days" would have counted.
  - A plural bug ("cases" → "cas") was found by a smoke test and fixed before building.
- D3 also applied to data search (my reading of D2's "counts updated").
- Answer serialization: Bob sometimes writes `", "` between objects and `":"` inside them. Two mixed separator styles were added to the style detection; before the fix, 5 data-search items (all rep009) were dropped as "serialization not reproducible". Technical, not a rule change.
- Blind-check pool: all validated baits (main and hold-out), as in the A01 generator.
**Item flow (plan §23.4; count mode `answer_noun`):**

| | candidates | baits built | validated (rules 1–3) |
|---|---:|---:|---:|
| extraction, main | 64 | 20 | 20 |
| extraction, hold-out | 8 | 4 | 4 |
| data search, main | 89 | 87 | 87 |
| data search, hold-out | 12 | 12 | 12 |
| **main total** | **153** | **107** | **107** |

- Extraction drops (48):
  - no eligible record, D5: 26 (24 main / 2 hold-out);
  - Bob's text names every eligible record: 15 (14 / 1);
  - answer size outside the count rule: 3;
  - object-list answer: 3;
  - reasoning lists answer IDs: 1.
- D4 used the second-ranked record in 2 items; 22 use the first.
- Comparison with A01 under the plan's literal rule (`plan_nouns`, D4 active): 15 validated extraction baits (13 main / 2 hold-out). Under A01 overall: 13.
- Data-search drops (2, main): no eligible relaxation adds exactly one row (rep020_e06, rep025_e04).
- All 99 data-search baits relax a date bound:
  - `opened_date` 45, `event_date` 31, `start_date` 23;
  - 96 upper, 3 lower (the 3 where the upper bound 2025-12-31 admits nothing).
- `bob_states_condition`: 91 of 99 (reasoning 77, reasoning + framing 14); 8 unflagged.
- Count edits: 9 data-search items had a count incremented in Bob's saved reasoning (e.g. "22 matching procurement requests" → "23"). In 19, a complete answer list in the framing was updated.
- **The main sample is 107, below the plan's minimum of 120 (§8.1). Per A02, no fallback decision was taken.**
**D5 (counts in `docs/deviations.md`):** 13 manifest tasks have no eligible record.
- 9 fail "exclusion criterion visible in the sentence" (lexical proxy).
- 4 fail "between two valid records".
- None fail "invalid record exists" or "exclusion clause exists".
- Among candidates: 17 + 9 = 26.
**Blind-check package (task 3):**
- 20 pairs: 16 data search, 4 extraction (largest remainder of 99 : 24); seed 2026; 760 KB of Markdown.
- Key SHA-256 `3240889f5f9912c86b3926de75871e3bffc6735076293ca69fed3a6394b0327d` (also in `blind_check/key_sha256.txt`).
- Leak check: no "bait" string and no item ID in any pair file.
- I did not open the pair files beyond the automated checks.
**Checks performed:**
- `pytest`: 235 passed (full suite, 38 s).
- `python -m src.replay.build_baits`: output as in the table above.
- Diffs read by eye:
  - rep004_e06 (date bound, row inserted at its result position, answer list and "22 → 23" count);
  - rep013_e05 framing (answer list updated).
  - The 3 lower-bound cases were checked by listing them.
**Task 4:** `LICENSE` is the standard MIT License text, "Copyright (c) 2026 Nick Wagner", as plan §14 requires. Not changed.
**Did not work:** see Decisions (rejected noun set, plural bug, separator styles). All were fixed before the final build; no output from a faulty version was kept.
**State / limitations:**
- The validity of the visible error rests on rules 1–3 and Nick's blind check (pending).
- No bait has been read in full by a human beyond the diffs above.
- Every data-search bait is the same error type (a date window extended by a few days to weeks). Whether that is visible enough is exactly what R4/R4n and the blind check measure.
- The sensitivity subset for `bob_states_condition` is small (8).
**Next (decisions for Nick, not started):**
1. Main sample of 107 is below 120.
2. Data-search bait homogeneity (relaxation order).
3. D3 applied to data search.
4. Blind check (package ready).
5. R0 identity mismatch (see `devlog/02_pilot.md`).
**Cross-references:** `docs/deviations.md` D2–D5; plan §§8.1, 8.3, 8.6 (right-reason), 23.4; `devlog/02_pilot.md` (A02 pilot entry).
