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
