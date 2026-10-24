# DEVLOG 04 — Hysteresis extension (Study 2)

## Scope

Trajectory prefixes and branching, changed communication conditions, controlled partner behavior, technical integrity, longitudinal outcomes, expenditure, and analysis of persistence. Refer to `PROJECT_PLAN.md` §9 for the study design and §12 for budgeting.

## Initial state — starter file, not a work entry

No Study 2 work or result is recorded here. Its inclusion in the plan does not authorize launch, paid activity, or sample-size changes.

## Entries (append chronologically below)

<!-- Use the entry format in ../CLAUDE.md. Do not overwrite past entries. -->

## 2026-10-24 11:06–11:30 UTC — Claude Code (Opus 5.5), session A04 — Task 5: Study 2 implementation plan (no building, no calls)

**Assignment / authorization:** Nick's correction at about 11:06 UTC (verbatim in `assignments/A04_addendum_D17_D19.md`): D17 withdrawn; Study 2 will be built right after A04; task 5 becomes an implementation plan with build steps, time, wall time and cost for P8 and for 40 and 50 pairs at 4/8/16/32 workers, rate limits if readable without a paid call, and the earliest launch. No building, no calls.
**Built or changed:**
- `docs/study2_implementation_plan.md`: the plan.
- `docs/deviations.md`: the D17 withdrawal entry. D17 itself stays in history: it was already committed and tagged in prereg-v1 when the correction arrived.
**How it was done:**
- A read-only subagent read the upstream runner, resume, prompts, and controlled-peer code, and measured the 50 published unconstrained Flash-Lite traces (`scratch/a04/study2_findings.md`, `scratch/a04/study2_trace_stats.py`, both local).
- I spot-checked: `--resume-from` is on `experiments/runner.py:284` and absent from `cli.py`; rerunning the helper gives 65.27 / 163.99 USD (with / without cache) for the 50 traces.
- Timing comes from our own P7 and main-run calls. Rate limits come from Google's public rate-limit page, read via a tool summary.
**Key figures (estimates; see the plan):**
- Build about 8.5–9 h sequential, about 5–6 h with parallel builders.
- Per sequence about 633 calls, ≤ 3.9 USD with cache and ≤ 10.1 without.
- 40 pairs: ≤ 156 / ≤ 404 USD. 50 pairs: ≤ 195 / ≤ 505 USD.
- Wall time for 40 pairs: 8.8 / 4.4 / 2.2 / 1.1 h at 4 / 8 / 16 / 32 workers (50 pairs: 11.0 / 5.5 / 2.8 / 1.4 h). Critical path per sequence about 24 min.
- Rate limits are per project and tier, viewable in AI Studio only; not readable here.
- Earliest launch: Saturday about 20:00 UTC.
**Did not work / not measured:** the constrained Flash-Lite traces are not downloaded, so the constrained arms are bounded by the unconstrained figures. Wall time is not stored in the published traces.
**Open for Nick:**
- budget conflict with plan §12 (no-cache projection above the hard cap);
- RAW LOG PART mapping onto rounds;
- the project's rate limits from AI Studio;
- a Study 2 preregistration record.
**Next:** build after A04, on Nick's go.
**Cross-references:** plan §§9, 10 (P8), 11, 12; `docs/deviations.md` (D17 withdrawal).

## 2026-10-24 11:45–12:50 UTC — Claude Code (Opus 5.5), session A05 — Tasks 1–2: Study 2 build, analysis code, dry run (no API call)

**Assignment / authorization:** `assignments/A05_study2_build_launch.md` (Nick, verbatim; commit `192f5c8`), tasks 1–2, with decisions D20–D23. Until A04's close-out (`08e2a7e`, about 12:16 UTC) only Study 2 paths were touched. The queued shared edits (deviations, caps, requirements) were applied after that.
**Built or changed:**
- `src/hysteresis/upstream_tree.py`: dedicated working copy `work/study2/upstream` (local, git-ignored), made with `git archive` of the pinned commit 5afb2c5 (experiments/, task/, LICENSE). A content hash goes in a marker file and is re-verified at every launch. `experiments` may be imported from the copy or from the submodule only if the submodule is clean at the pin (`src.runner` imports it first).
- `src/hysteresis/run_arm.py`: one arm × one sequence through upstream's own runner functions (`build_run_parser`, `validate_run_args`, `_load_selected_tasks`, `_episode_policy_sequences`, `_run_selected_episodes`), with cwd = the copy.
  - Arms and spans: prefix `throttled:*`, first 5 pairs of the unchanged 10-pair manifest (upstream has no stop-after-N option, and resume needs the same manifest path); A′ `throttled:*`, resumed from the prefix; B and PC `throttled:5,no-throttle:*`, resumed from the prefix; C′ `no-throttle:*`, fresh.
  - Settings are Shi et al.'s, and the test compares them against a published trace's run_config. `--no-preflight` is set as in upstream `cli.py`, so the wrapper makes no probe call.
  - Checks upstream resume skips: models, sampling, litellm.
  - Sidecar `study2_meta.json`: arm, seq, git head, upstream copy hash, argv, resume source + sha256, B source + sha256, status, pid, UTC times, episodes.
  - SIGTERM is recorded as a failed status.
- `src/hysteresis/status_line.py`: wraps `episode_runner._prepare_pair`. From episode_index 5, it appends "\n\n" + the plan §9.1 line to each agent's `judging_prompt` (the communication opening the peer receives): the limited text if the episode is throttled, otherwise the open text. Placement (last paragraph of the opening) is an implementation choice; the plan fixes only the text and the episodes.
- `src/hysteresis/guard.py`: replaces `experiments.agents.completion`, the only model call site. Before each request it checks the STOP file and the ledger: P8 group cap 5, Study 2 stage cap 250, hard cap 330, with a reserve of 0.06 USD × worker slots. After each response it checks `response_model` (expected `gemini-3.1-flash-lite`; a change writes STOP).
  - Stops are a `BaseException`, because upstream retries every `Exception`.
  - Spend comes from all upstream `llm_usage.jsonl` journals under `results/study2`, priced with `configs/prices.yaml`, plus the live ledger over `results/raw`, re-read every 60 s.
- `src/hysteresis/partner_control.py` (built by a subagent, reviewed and amended by me): converter from the finished B run.json to upstream's controlled-Bob cache, and four idempotent patches.
  - The D22 message policy `raw-log-full`.
  - D22 message validation.
  - Per-episode verdict replay via `dataclasses.replace(config, controlled_bob_verdict=...)`.
  - A relaxed live→controlled resume check, covering exactly the controlled-Bob keys and Bob's prompt.
  - Bob's slot is rebuilt with upstream's `_prepare_pair` plus B's task-phase fields. It is verified at build time: B's get_log string; upstream's `evaluate_saved_artifact` reproduces B's evaluation.
  - My amendment: if Bob made no successful get_log in a B episode, he still sends the formatted private raw log, i.e. the string get_log would have returned and the one `strict_full` uses. Before, such a sequence raised. **Untested** (the mock always calls get_log).
- `src/hysteresis/scheduler.py`, `scripts/study2/launch.py`: resumable scheduler, state read from disk.
  - Priority B, PC, prefix, C′, A′. A′/B start after the prefix exits; PC after B exits.
  - Worker limit can be changed while running (file `WORKERS`); a STOP file blocks launches; at most 3 launches per arm.
  - Orphan detection: launch events without an exit whose process is alive. The run that counts is the earliest-started complete run (an outcome-independent rule).
  - Event log `scheduler.jsonl`.
- `scripts/study2/monitor.py`: operational only (calls, errors, 429s, response models, spend, cached share, throughput, wall time, arm states). It reads no message, verdict or outcome.
- `scripts/study2/fix_n.py`: the D21 rule, checking n against both the remaining Study 2 cap and the remaining hard cap. It refuses if P8 is incomplete or if Study 2 spend outside P8 exists.
- `scripts/study2/run_list.py`, `scripts/study2/interrupt_check.sh`.
- `src/hysteresis/analysis.py`, `scripts/study2/analyze.py` (subagent; reviewed by me, reading the primary, H7, bootstrap and row code):
  - primary paired t-test + sequence bootstrap (10,000, seed 2026), B − C′, episodes 6–8, both directions;
  - H7 (PC − B, Alice direction): procedure mirrors the primary and is labelled as needing Nick's confirmation;
  - plan §9.3 secondaries and the status-line check;
  - the CLI refuses outcome statistics without `--confirm-run-complete` and complete arms; `--status-line-only` mode.
- `src/hysteresis/mock_model.py`: deterministic mock (SYNTHETIC) that plays all phases; IDs depend on the request; optional request-hash log.
- Tests: `tests/test_study2_build.py` (16), `tests/test_study2_partner_control.py` (10, subagent), `tests/test_study2_analysis.py` (22, subagent).
- Shared files, after A04: `configs/caps.yaml` (D20), `docs/deviations.md` (D20–D23), `requirements.txt` / `requirements.lock.txt` (scipy 1.18.1 installed into `.venv`, numpy unchanged).
**Checks performed (all mock or local, no API call):**
- The upstream copy is byte-identical to the submodule (`diff -rq`).
- **Resume equivalence:** a C′ run resumed from its own 5-episode record sends byte-identical requests for episodes 6–10 to the uninterrupted run (90/90 request hashes) and yields identical results. Branching at episode 6 therefore adds no context difference between the resumed arms (A′, B, PC) and the continuous C′.
- Status line: present exactly once from episode_index 5, with the right text per arm, and nowhere before (tests + analysis check: PASS, 180 rows on the 2-sequence dry run).
- **Check A (subagent, reran by me):** `verdict_rows` reproduces the published verdict table on 1000/1000 rows (strict_full, multipiece, peer_correct, accept), and the episodes 6–8 sequence mean 0.653 / SD 0.240.
- Simulated null false-positive rate 0.048–0.050; power at 15 pp 0.75–0.83 (40 pairs).
- **Full dry run:** `scripts.study2.launch --group dry --seqs 1-2 --workers 8 --backend mock`: 10/10 arms in 64 s, 990 mock calls, 0 errors. Then run list → status-line check PASS → `analyze --confirm-run-complete` (synthetic numbers, not results) → monitor.
- **Interruption check:** the scheduler and a C′ child were killed at episode 2–3, then the scheduler restarted. The C′ run resumed from its boundary; no duplicate runs; 11 launches for 10 arms.
- `pytest` full suite before the PC amendment: 394 passed (361 s). Study 2 files after all changes: 16 + 10 + 22 passed.
**Did not work (fixed):**
- the journal name is `llm_usage.jsonl`, not `llm_usage_journal.jsonl`;
- the mock's reflection is detected by the missing `tool_choice`;
- relative paths broke after the chdir;
- duplicate launches after a scheduler restart (orphans not yet visible), fixed with orphan detection;
- PC could launch while B's process was still writing its metadata (the data was already final), fixed: dependents wait until the process is reaped.
- I killed my own shell three times with `pkill -f` patterns that matched my command line. No study process was affected; the A04 main run ended normally at 2,330/2,330.
**State / limitations:**
- The mock's raw logs are short, so under the 200-character limit the mock still transmits them. The constrained error path is exercised only in unit form.
- Slot reconstruction with written test files and database/record tools is guarded by build-time checks but not exercised on real data until P8.
- Raw-run storage: a 10-episode run.json is about 3 MB gzipped, so a full Study 2 is roughly 0.6 GB. Committing it needs a decision (see Next).
**Open for Nick:** (1) H7 procedure (paired t-test + bootstrap, Alice direction, PC − B, episodes 6–8, as the primary); (2) storage of Study 2 raw run files in git; (3) the status-line check counts but does not fail on agents quoting the line in later messages.
**Next:** P8 live on rep001 (A05 task 3, cap 5 USD), now that the Study 1 main run is finished.
**Cross-references:** plan §§9, 12, 13, 23; `docs/deviations.md` D20–D23; `docs/study2_implementation_plan.md`.
