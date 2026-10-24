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
