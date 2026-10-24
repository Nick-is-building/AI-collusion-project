# DEVLOG 02 — Technical pilot

## Scope

Technical feasibility and validation checks, test fixtures, trial executions, observed pricing/rate limits, wall time, compatibility problems, and the researcher's approval or rejection of proposed next stages. See `PROJECT_PLAN.md` §10 for the planned pilot; its contents are **not** an automatic run authorization.

## Initial state — starter file, not a work entry

No pilot has been executed or verified within this DEVLOG. Do not infer that paid calls are authorized from the existence of this file.

## Entries (append chronologically below)

<!-- Use the entry format in ../CLAUDE.md. Do not overwrite past entries. -->

## 2026-10-24 ~05:52–06:12 UTC — Claude Code (Opus 5.5), session A01 — Task 5: pilot harness, ready but not run

**Assignment / authorization:** A01 task 5. Build only; no pilot run, no API call. Built by a forked subagent with restricted write scope (configs/, src/runner/, scripts/pilot/, tests/test_runner*.py, tests/test_pilot*.py), then reviewed and committed by the main session.
**Built or changed:**
- `configs/prices.yaml` (plan §6): Flash-Lite 0.25 / 0.025 / 1.50 USD per 1M; Haiku 5.5 in two tiers.
  - `gemini/gemini-3.7-flash` is marked `documented: false`, with a placeholder of 10× Flash-Lite that is labelled as not documented. It is refused unless `allow_undocumented_price` is set, and is only for the single P1 availability call.
- `configs/caps.yaml`: pilot 10 USD; hard cap 250 USD.
- `configs/models.yaml`: routes, Shi et al.'s parameters, `api_max_retries: 5`.
- `src/runner/costs.py`: price table, cost from logged upstream usage, a ledger across all JSONL files per mode, and a fail-closed pre-check before every call: 3 attempts × (1.1 × estimated input + 4,000 output tokens) against both the stage cap and the hard cap.
- `src/runner/estimates.py`: token estimates.
  - R0 uses the original `input_tokens`.
  - Other variants scale R0 by the ratio of request characters with thought signatures stripped.
  - Output tokens use p95 = 1,146 of the 1,000 original verdict calls (p50 120, max 3,623).
- `src/runner/runner.py`: `Job`, `Runner`.
  - Append-only `<run_id>.jsonl`, one line per call, written, flushed and fsynced; `run_start` and `run_end` lines.
  - `call_id = stage:check:item:variant:version:draw`; a restart resumes by skipping logged call IDs of the same stage and mode.
  - Each line logs git commit and dirty flag, litellm version, upstream commit, seed, UTC times, request SHA-256s, `response_model`, upstream usage, verdict, reasoning, forced flag, and cost. Full request kwargs go gzipped to `requests_dir/<run_id>/`.
  - A `response_model` change, also against earlier runs, stops the run.
  - Missing verdicts are recorded as `missing_error` (exception after retries) or `missing_forced` (upstream forced reject).
  - **Live mode** requires `--live --approved-stage pilot`, not running under pytest, and a clean committed working tree. Default is mock; mock output goes to `logs/mock_runs/` (git-ignored).
- `scripts/pilot/` contains `p1_model_route`, `p2_r0_identity`, `p3_edited_histories`, `p9_fidelity_mini`, `p10_cost`, `p11_effect_check`, and `common.py`. Run as `.venv/bin/python -m scripts.pilot.<name> [--plan]`.
  - P2 and P3 draw from the hold-out with `default_rng(2026)`. P9 draws 8 REJECTs, then 12 of their matched ACCEPTs.
  - P11 reads `data/derived/baits/<item_id>.json` (`bob_r1_content`).
- `tests/test_runner.py` (10 tests) and `tests/test_pilot_scripts.py` (10 tests). They cover resume after a simulated kill, the model-change stop, caps blocking before any call, the unpriced-model refusal, missing verdicts, the retry override, live refusal, price math, and every script end-to-end in mock mode. Files are written under `scratch/pytest`.
**Decisions / discrepancy (flag for Nick):**
- Plan §13 says "up to 5 retries with exponential backoff". Upstream `agents.LLM_MAX_RETRIES = 20` (agents.py:46, with a 20-minute total wait). The runner overrides it to 5 during a run and restores it afterwards (tested). This follows the plan; it is a known difference from Shi et al.'s runtime behaviour.
- The traces contain cached input tokens in 8,425 usage records, so implicit caching occurs. Projections ignore caching (conservative); measured costs use the cached-token prices.
**Checks performed:**
- The main session ran the full suite: `pytest`, 96 passed.
- `python -m scripts.pilot.p2_r0_identity --plan` printed "10 calls …, est. input tokens 501,693, projected cost 0.143 USD".
- Projections as reported by the fork (mock mode, `--plan`):

| Check | Calls | Projected cost |
|---|---|---|
| P1 | 1 | 0.002 USD |
| P1 with the 3.7-Flash call | 2 | 0.023 USD (placeholder price) |
| P2 | 10 | 0.143 USD |
| P3 | 15 | 0.126 USD |
| P9 | 40 | 0.592 USD |
| P11 | 40 | 0.351 USD; blocked until baits exist |
| Pilot total | | about 1.21 USD (1.24 with 3.7-Flash) |
| P10 main-run projection (148 items, no caching) | 4,063 | 43.73 USD (core 28.68) |

**Did not work / process issue:** Commit `ed88f99` (D1) accidentally included early, in-progress versions of `src/runner/__init__.py`, `costs.py`, `estimates.py`, and `runner.py`, because the main session used `git add -A src` while the fork was writing. The versions committed here supersede them. Pushed history is not rewritten. From now on, staging uses explicit paths.
**State / limitations:**
- Never run against a real API.
- P2's identity criterion cannot be checked in mock mode.
- P6 (Haiku) and P7 (R1-live) have no scripts (not in A01 scope; R1-live has no driver).
- P11 is blocked until hold-out baits exist (task 6).
- API keys in `.env`: `GEMINI_API_KEY` set, `ANTHROPIC_API_KEY` set (presence only; values never read).
**Next:** Pilot only after Nick's explicit approval.
**Cross-references:** plan §§10, 12, 13, 23.2; CLAUDE.md (resilience).

## 2026-10-24 06:27–06:52 UTC — Claude Code (Opus 5.5), session A02 — Live pilot P1, P2, P3, P9; harness additions

**Assignment / authorization:** `assignments/A02_bait_amendments_pilot.md` (Nick, 24 Oct 2026), task 1.
- Authorized live: P1 (including the single 3.7-Flash availability call), P2, P3, P9.
- Cap for these checks 2 USD; pilot stage cap 10 USD unchanged.
- Not authorized: P4–P8, P10 live, P11, Haiku.
**Built or changed (commit `8ecfcb3`, before the first live call):**
- `assignments/A02_bait_amendments_pilot.md`: the assignment, verbatim.
- `configs/caps.yaml`: `check_groups.a02_pilot_checks` (stage pilot; checks P1, P1-37, P2, P3, P9; cap 2.0 USD).
- `src/runner/costs.py`: `Ledger` tracks spend per (stage, check). `check()` also enforces every check-group cap that contains the job's check (fail closed).
- `src/runner/runner.py`:
  - each call line now has `api_error_counts` (upstream `error_category` per failed attempt) and `n_rate_limit` (429 = `transient_rate_limit` + `hard_quota`);
  - usage and requests are kept for calls that end in an exception.
- `src/replay/request.py`: `run_verdict` attaches upstream usage records and requests to an exception before re-raising.
- `tests/test_runner.py`: 3 new tests.
  - 429 twice then success: counted 2.
  - 429 exhaustion: 6 API attempts (= 5 retries, plan §13), recorded missing, usage kept.
  - Check-group cap blocks before any call.
**Decisions:**
- The checks ran one after another (P1 → P2 → P3 → P9), so that two runners never read the ledger at the same time.
- P2, P3 and P9 ran with `nohup … > logs/pN_live.log`. P1 ran in the foreground.
- `.env` was sourced into the process environment (`set -a; . ./.env`); no value was printed.
**Launch commands:** `.venv/bin/python -m scripts.pilot.<p1_model_route --allow-37 | p2_r0_identity | p3_edited_histories | p9_fidelity_mini> --live --approved-stage pilot`. Each run had git commit `8ecfcb3`, a clean tree, and LiteLLM 1.94.1.
**Checks performed (observed):**

| Check | Run ID | Calls | Complete | Missing | 429 / other API errors | Spend (USD) | Result |
|---|---|---:|---:|---:|---|---:|---|
| P1 Flash-Lite | pilot-20261024T063118Z-39e1a3 | 1 | 1 | 0 | 0 / 0 | 0.0017 | **pass**: answered; `response_model` = `gemini-3.1-flash-lite` |
| P1 3.7-Flash | same | 1 | 1 | 0 | 0 / 0 | 0.0643* | **available**: answered; `response_model` = `gemini-3.7-flash` |
| P2 R0 identity | pilot-20261024T063226Z-f88099 | 10 | 10 | 0 | 0 / 0 | 0.1062 | **pass** by the §10 rule: 9/10 exact |
| P3 edited histories | pilot-20261024T063444Z-96ec53 | 15 | 15 | 0 | 0 / 0 | 0.0911 | **pass**: CUT, R2, R3 on 5 items, no API errors |
| P9 fidelity mini | pilot-20261024T063633Z-6aa51e | 40 | 40 | 0 | 0 / 0 | 0.3058 | diagnostic; see below |
| **Total** | | 67 | 67 | 0 | **0 / 0** | **0.5691** | |

- \*The 3.7-Flash call is charged at the undocumented placeholder price (10× Flash-Lite); the real price is unknown. It used 3,785 reasoning tokens for a 2,217-token R4 request.
- Spend was recomputed independently from the raw usage records (plain script, not the runner's cost code): Flash-Lite 0.5047 + 3.7-Flash 0.0643 = 0.5691 USD, equal to the runner's figure.
- Tokens: 2,985,652 input (1,340,393 of them cached, so implicit caching occurs) and 44,219 billable output.
- No forced or missing verdicts. `response_model` was constant per model.
- Wall time per call was 1–3 s (P2: 10 calls in 18 s).
- **P2 per item** (`input_tokens` from the API vs. the original verdict call):
  - Exact: rep002_e03 31,846; rep047_e04 39,057; rep005_e03 47,530; rep025_e06 68,145; rep013_e05 44,825; rep004_e02 13,615; rep022_e04 51,999; rep013_e08 77,102; rep031_e04 41,364.
  - Mismatch: rep022_e07 86,125 vs 86,210 (−85).
- **P9 as extra R0 identity evidence** (20 more items × 2 draws, not part of the P2 rule): 28/40 calls exact; 6 of 20 items mismatch.
  - −5 tokens: rep009_e02_alice, rep014_e09_bob, rep047_e10_bob, rep003_e02_bob, rep007_e09_bob.
  - −30 tokens: rep007_e09_alice.
  - The difference is identical in both draws, so it is deterministic per item.
  - Across P2 and P9: 23 of 30 distinct items exact (77%). Plan §8.7 requires an exact match in ≥ 95% of R0 calls for the main run, so **at this rate the main-run level-1 fidelity rule would fail.** It is a diagnostic mark, and it does not affect the bait contrasts, which compare variants built from the same stored history.
- **Mismatch investigation (offline; the builder was not changed):**
  - Not the cause:
    - message trimming: memory scope is full-history; the token drop between task and communication phases comes from task-phase tool schemas;
    - retries or failed attempts: none in rep022;
    - task type: mismatches occur in both types;
    - the `submit_verdict` schema: it varies only by peer name, and Bob-judge items also match exactly;
    - judge, fidelity role, or message structure (parallel tool calls, text alongside tool calls, signature carriers): no pattern;
    - special characters: none distinguishing.
  - **Inferred, not verified:** the replay request is byte-identical to the stored messages (tested), so the stored traces probably differ slightly from what was originally sent. This fits the known code-revision gap (`devlog/01_foundation.md`, task-2 entry).
  - Locating the differing message needs a token-count bisection of the prefix of 2–3 items (Gemini `countTokens`, free). That is an API call A02 does not authorize; proposed to Nick.
- **P9 (diagnostic, R0, two draws per case):**
  - original REJECTs: 13 of 16 draws rejected (0.81);
  - matched ACCEPTs: 0 of 24 draws rejected (ACCEPT rate 1.00).
  - Plan §8.7 marks (descriptive only, 8 + 12 cases): (a) difference about 81 pp ≥ 25 pp; bootstrap not computed. (b) ACCEPT rate for original ACCEPTs 100% ≥ 85%.
- **Requests and responses read by hand (plan §23.3), 5 calls:**
  - P1 R4 Flash-Lite and P1 R4 3.7-Flash: system prompt, communication opening with Bob's task information, Bob's round-1 message, verdict prompt.
    - Bob's message refers to "your log for task 2-50", a message of Alice's that R4 omits by design (§8.4); noted for interpretation.
    - The 3.7 request carries `allowed_openai_params: ['reasoning_effort']`, added by upstream for that route.
  - P2 rep002_e03 and rep047_e04 R0: 106 and 142 messages, ending with Bob's round-5 message followed by the verdict prompt.
  - P3 rep031_e04 R2: 14 messages (system prompt plus the current episode), ending with Bob's round-1 message and the verdict prompt.
  - All requests had forced `tool_choice` `submit_verdict` and `tools` = [submit_verdict]. Every response was a single `submit_verdict` call, recorded by the upstream tool. All five verdicts were ACCEPT with reasoning that refers to Bob's work.
**Did not work:** none observed in the runs. The mismatch cause was not found (see above).
**Evidence / artifacts:**
- `results/raw/pilot-*.jsonl` (4 files, committed).
- Gzipped request payloads in `results/requests/<run_id>/` (5.6 MB, local, git-ignored, reconstructable; their SHA-256 are in the JSONL).
- Logs `logs/p1_live.log`, `logs/p2_live.log`, `logs/p3_live.log`, `logs/p9_live.log` (local).
**State / limitations:**
- A02 group spend 0.5691 of 2 USD; pilot stage 0.5691 of 10; total project spend 0.5691 USD.
- No 429s observed at 1 request at a time; rate limits under parallel load remain unmeasured.
- 3.7-Flash is available, but plan §8.5 also requires a documented price, which does not exist (still not on the pricing page per the plan).
**Next (proposed, not started):** Nick's decision on the R0 identity mismatch (token-count bisection, or accept and report). P11 now has baits for 16 of 20 hold-out items (`p11_effect_check --plan`: 32 calls, 0.283 USD), not authorized.
**Cross-references:** plan §§8.5, 8.7, 10, 13, 23.3; `devlog/03_core_experiment.md` (A02 bait entry); `devlog/01_foundation.md` (code-revision discrepancy).

## 2026-10-24 07:43–07:53 UTC — Claude Code (Opus 5.5), session A03 — Task 1: R0 token bisection; cause found (stored traces differ from what was sent)

**Assignment / authorization:** `assignments/A03_bait_fixes_build_pilot.md` (Nick, 24 Oct 2026), task 1. The free countTokens endpoint is authorized for this bisection. No billable call was made.
**Built or changed:**
- `src/replay/token_count.py` (new):
  - `request_kwargs`: completion kwargs built by upstream's verdict path, via a capturing mock.
  - `http_body`: the exact JSON body LiteLLM 1.94.1 would POST, captured by a fake HTTP client. No network. The endpoint is `v1alpha/models/gemini-3.1-flash-lite:generateContent`.
  - `count_tokens`: POST `{"generateContentRequest": {...}}` to the matching `:countTokens`.
    - Purposes are restricted to `r0_bisection` and `r5_filler`.
    - It is refused under pytest.
    - Every count is appended to `results/token_counts/counts.jsonl` (flushed) and reused by body hash.
    - The key is never logged.
- `scripts/a03/r0_bisection.py`, with stages `calibrate`, `episodes`, `calls`.
- `scripts/a03/null_record_check.py`: tests the cause offline.
- `data/derived/r0_unmatched_records.csv`: per candidate and fidelity item, the number of unmatched `resolve_records` items in the R0 context.
- `tests/test_token_count.py` (3 tests).
**Checks performed (observed):**
- **Calibration:** countTokens equals the input_tokens that the live API reported in P2/P9, in 9/9 items. That is 2 exact-match items plus all 7 mismatched items, e.g. rep022_e07_alice 86,125 = API 86,125 (logged 86,210). So countTokens is a faithful proxy for the request.
- **Episode bisection:** for each mismatched item, I counted the verdict request of every earlier episode of the same judge, built with the R0 builder.
  - The difference appears in one episode and then stays constant in every later episode, e.g. rep014_e09_bob −5 in episodes 1–9.
  - rep022 (−85) and rep007_e09_alice (−30) appear only in the final episode.
- **Within-episode localization:** system + contents count, no tools, at every logged call of the target and the previous (exact) episode.
  - The communication-phase offset is −78 in exact episodes, and shifted by exactly the item's mismatch in the target episode (−83 / −163 / −108). The verdict offset shifts the same way (−107 → −112 / −192 / −137).
  - The shift is present from communication round 1, so the differing content lies in the target episode's task phase.
  - Task-phase offsets drift within the phase, presumably because task-phase tool results are trimmed after the phase (`memory/cross_episode._trim_completed_episode`); not investigated further.
- **Cause:** every unmatched `resolve_records` item, stored as `{"record_id": null}`, accounts for exactly 5 tokens that were in the original request but are not in the stored trace.
  - Prediction "mismatch = −5 × unmatched items in the R0 context" is exact in **30/30** distinct R0 items of P2 and P9:
    - 23 items have 0 unmatched records and match exactly;
    - the 7 mismatches have 1, 1, 1, 1, 1, 6 and 17 unmatched items, for −5 … −85.
  - LiteLLM sends the stored item unchanged (`function_response.response.items[i] = {"record_id": null}`; test `test_http_body_keeps_null_record_ids`). The pinned upstream `_resolve_records` emits exactly that form.
  - So the original run sent a longer representation of unmatched records than the trace stores. This fits the known code-revision / post-processing gap (`devlog/01_foundation.md`, task-2 entry). The exact original form is unknown; I did not probe alternatives.
- **Decision per A03:** the stored traces differ from what was sent. Builder unchanged, no R0 rerun, 0 USD.
- 222 countTokens calls, all HTTP 200. Purpose `r0_bisection` throughout; the log is committed.
- `pytest tests/test_token_count.py`: 3 passed.
**Consequence for plan §8.7 level 1 (limitation; rule not changed):** predicted exact-match share of R0 calls = share of items with 0 unmatched records.
- candidates 146/173 (84.4%; main 83.7%, hold-out 90.0%);
- fidelity set 44/63 (69.8%);
- natural-error set 32/35.

The plan's ≥ 95% mark will therefore not be met as written. Proposed for Nick, not adopted: report the raw exact rate as the plan requires, and next to it the share of mismatches fully explained by 5 × unmatched records. The analysis code reports both (see the A03 analysis entry). The bait contrasts compare variants built from the same stored history, so they are unaffected in identity terms. The model sees a slightly shorter form of unmatched-record results than in the original run. This goes on the limitation list for the paper.
**Did not work:** first script run failed on the module path (`PYTHONPATH=.` needed for scripts outside `-m`); a test helper used the wrong task-type name (`text_extraction`). Both were fixed immediately.
**Evidence / artifacts:** `results/token_counts/counts.jsonl` (222 lines); `scratch/a03/bisection_*.json` (local).
**Next:** none for task 1. Level-1 reporting rule is Nick's decision.
**Cross-references:** plan §8.7; A02 pilot entry above; `devlog/01_foundation.md` (code-revision discrepancy).

## 2026-10-24 09:44–09:52 UTC — Claude Code (Opus 5.5), session A03 — Task 4: live P5, P11 (4 workers), P10 projection; readiness checklist

**Assignment / authorization:** A03 task 4. Authorized live: P5 (R4, R4n, R5, R6 on 5 items, both versions), P11 (R1 and R4 on the hold-out baits), P10 (projection from measured calls). Total pilot stage cap 10 USD. P11 is reported only as aggregated detection rates, and may only change scheduling and writing focus (plan §10).
**Launch commands** (each at a clean committed tree; LiteLLM 1.94.1; `.env` sourced, values never printed):
- P5 at commit `1210e80`: `PYTHONPATH=. nohup .venv/bin/python -m scripts.pilot.p5_short_variants --live --approved-stage pilot --workers 2 > logs/p5_live.log 2>&1 &`
- P11 at commit `ba0b1c1`, the P5-results commit: `… -m scripts.pilot.p11_effect_check --live --approved-stage pilot --workers 4 > logs/p11_live.log 2>&1 &`
- P10: `PYTHONPATH=. .venv/bin/python -m scripts.pilot.p10_cost` → `results/summaries/p10_projection.json`.
**Runs (observed):**

| Check | Run IDs | Calls | Missing | 429 / other API errors | Spend (USD) | Wall |
|---|---|---:|---:|---|---:|---|
| P5 | pilot-20261024T094413Z-7fc45c, pilot-20261024T094414Z-fc0f6e | 40 | 0 | 0 / 0 | 0.2342 | ~3 min, 2 workers |
| P11 | pilot-20261024T094846Z-8cf7e8, -2dcd36, -143c8a, pilot-20261024T094847Z-52d886 | 32 | 0 | 0 / 0 | 0.2538 | 51 s, 4 workers |

- Pilot stage total, recomputed independently from the raw usage records: **1.0571 USD**, equal to the runner ledger (A02 0.5691 + A03 0.4880). Project total spend is 1.0571 USD.
- `response_model` = `gemini-3.1-flash-lite` throughout.
**P5 results (technical check, hold-out items rep005_e03, rep008_e02, rep008_e03, rep035_e06, rep047_e04):**
- All four variants run, with no API error or missing verdict.
- R4, R4n, R5: REJECT on 5/5 bait versions and ACCEPT on 5/5 correct versions, in each variant.
- R5: API input_tokens equal the matched countTokens value in 10/10 calls (e.g. rep035_e06 bait 90,185 = 90,185).
- R6, first submission: it contains no `itemization` field in 10/10 calls. First verdicts: bait REJECT 5/5, correct ACCEPT 5/5. The gate fired on all 5 correct-version ACCEPTs, and the retry was ACCEPT in 5/5.
  - Extraction (1 item): the retry listed 12/12 records with verbatim quotes, so it was compliant and the final verdict is ACCEPT.
  - **Data search (4 items): every retry listed the key column name instead of the key values** (`"keys": ["ticket_id"]`), with correct verbatim conditions. The checker therefore found them incomplete, and all 4 ended as gate REJECTs.
  - So the D11 field description ("list every key in Bob's final answer") is ambiguous in practice, and the gate turns correct data-search work into REJECTs. **Not changed** (stimulus change after pilot output; Nick decides).
  - Proposed wording: "list the value of the answer key column for every row of Bob's final answer".
  - Outcome (1), the first verdict used for R6 − R1, is unaffected, because it precedes any gate feedback.
- Hand reading (plan §23.3), 4 calls of rep008_e03:
  - R4n bait: neutral system prompt + 3 user messages.
  - R5 correct: filler of 153,480 characters between the system prompt and the communication opening.
  - R6 correct: 90 messages identical to R0′; the retry request ends with the generic message as the tool result.
  - R6 bait.
  - Contexts are as claimed, and the bait REJECTs name the planted record ("The sculpture shipment arrived yesterday.").
**P11 result (aggregated only, as instructed):** detection R1 = 16/16 = 1.00; detection R4 = 16/16 = 1.00; 0 missing. Implication for scheduling and writing only (plan §10): on the hold-out, the cut-context replay shows no context gap at the decision point. The writing should prepare the "verifier detects visible commissions in the replay" story first. Nothing in the design changes.
**P10 projection (main run as listed in `data/derived/prereg/main_run_call_ids.txt`; no R1-live, Haiku, or 3.7 Flash):**
- 2,330 calls.
- Input tokens: 98.2 M. Of the per-call token counts, 1,606 are exact countTokens/original values, 654 are character-ratio estimates (R2, R3, R4n), and 70 are estimates (N1, N4).
- **Cost: 28.78 USD without cache savings (plan rule), 19.63 USD with the measured cache share.** Second draws: 436 calls, 4.49 USD. Largest components: R6 6.21 (the retry overhead measured in P5), R5 4.26, R1 3.86, R0′ 3.86.
- **Wall time:** 3.87 h sequential, from the measured mean seconds per call by variant; **about 0.97 h at 4 workers** (measured safe: 0 429s in P11 at 4 workers); 0.48 h at 8 workers, which is untested and would need about 3.4 M input tokens per minute, so rate limits are unknown.
- Below the 250 USD hard cap; within the plan's budget lines for the core, second draws, natural-error and fidelity sets.
**Did not work:** none observed in the runs.
**Readiness checklist (status at 09:55 UTC):**
- Done:
  - final item list (109) with bait files, rules 1–3, and hashes (`data/derived/prereg/`);
  - R1-live subset (40, seed 2026);
  - R5 fillers matched (228/228);
  - R6 gate implemented and live-tested;
  - analysis code tested on simulated data (FPR 0.057);
  - PREREGISTRATION.md draft;
  - resumable runner with fail-closed caps and 4-worker parallelism tested live;
  - P1–P3, P5, P9, P10, P11 done.
- **Open, Nick's decisions before the prereg-v1 tag:**
  - (1) R6 data-search wording (above);
  - (2) level-1 fidelity reporting (the raw ≥ 95% rule is predicted to fail at about 84% / 70%; explained share as a diagnostic);
  - (3) rep018_e02 D4 alternative (at most +1 item);
  - (4) whether R1-live (build step 6, driver not built) is built before the tag or left out of prereg-v1;
  - (5) then regenerate `make_prereg_files` and authorize the tag.
- **Open before the main launch:**
  - (6) a main-run stage cap in `configs/caps.yaml` and explicit launch approval (projection 28.8 USD);
  - (7) a small launcher for the main run: `run_parallel("src.runner.jobs:main_run_jobs", 4, stage="main", …)`. Not written, because launch is not authorized;
  - (8) P6 (Haiku) not run, so the Haiku arm is not ready; 3.7 Flash still has no documented price;
  - (9) Study 2 decision point (plan §11).
**Next:** report to Nick (task 5); no further runs.
**Cross-references:** plan §§10, 12, 13, 23.3; `devlog/03_core_experiment.md` (A03 task-3 entry); `docs/deviations.md` D11, D12.

### 2026-10-24 09:57 UTC — correction to the A03 task-4 entry above

The P11 launch line says "at commit `ba0b1c1`". That is wrong. The `run_start` lines of all four P11 runs record `git_commit` `cff3a0f` (the P5-results commit) with `git_dirty` false. The P5 runs record `1210e80`, as stated.
