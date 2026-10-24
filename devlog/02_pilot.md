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
