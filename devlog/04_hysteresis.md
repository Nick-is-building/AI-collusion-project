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

## 2026-10-24 12:50–13:00 UTC — Claude Code (Opus 5.5), session A05 — Live provenance check scoped to Study 2 code (before P8)

**Assignment / authorization:** A05 tasks 3/5 need live launches while session A06 edits other tracked files in the same working tree.
**Built or changed:** `src/hysteresis/run_arm.py`: live mode no longer uses the whole-tree clean check (`src/runner/runner.assert_live_allowed`). It requires instead: not under pytest; `--approved-stage study2`; and no uncommitted change in the paths a Study 2 run executes (`PROVENANCE_PATHS`: src/hysteresis, scripts/study2, src/runner, src/upstream.py, src/reanalysis, src/__init__.py, configs, third_party). The whole-tree dirty flag and the Study 2 path status are both recorded in `study2_meta.json`. `tests/test_study2_build.py`: the subprocess helper keeps `PYTEST_CURRENT_TEST`, so live mode is refused in every test.
**Decisions:** a technical provenance rule, with no scientific change. Without it, any A06 edit to a tracked file would make Study 2 launches fail.
**Checks performed:** `pytest tests/test_study2_build.py`: all passed (output in the commit message).
**Next:** P8.

## 2026-10-24 ~12:55 UTC — Claude Code (Opus 5.5), session A05 — Nick's clarification on P8 (during P8)

**Assignment / authorization:** Nick, in the Claude Code session (verbatim in `PREREGISTRATION_STUDY2.md` §8): P8 on rep001 is pilot data and is not reused; rep001 runs fresh in the main launch; P8 outcomes are never looked at (use is limited to cost, cache share, wall time, errors, the status-line check); the extra sequence counts in the D21 cost calculation; record it in the preregistration.
**Built or changed:** `PREREGISTRATION_STUDY2.md` §8 (draft, untagged): the verbatim clarification and how the code meets it. No code change was needed. P8 lives under `results/study2/p8/` and the main run under `results/study2/main/`, and scheduler and run list read one group only. `fix_n.py` subtracts P8 spend from the remaining Study 2 cap. The status-line check prints PASS/FAIL only, and the monitor reads journals and metadata only.
**Checks performed:** none new. So far no P8 trace has been opened except the run logs' tool status lines (e.g. "send_message(err:MessageError: exceeds 200 char limit)" in the prefix log, seen while checking for errors).
**Next:** P8 completion, status-line check, D21.

## 2026-10-24 12:58–13:10 UTC — Claude Code (Opus 5.5), session A05 — P8 interruption: branch launches refused (provenance), scheduler relaunch loop; fixes

**Observed (P8, run `results/study2/p8/`):**
- The prefix finished at 12:58:49 UTC (rc 0).
- Every B and A′ launch then failed within about 10 s with `LiveNotAuthorized: Study 2 code paths have uncommitted changes (provenance): [' M configs/caps.yaml']`. Session A06 had added its own stage cap `a06: 10.0` to `configs/caps.yaml`, not yet committed.
- These launches died before `study2_meta.json`, so the scheduler did not count them as attempts and relaunched every ~10 s (about 10 launches each, 12:58:49–12:59:41).
- No API call was made by any of them: they fail before the model is reached, and no journal exists under B/ or A′/.
- I stopped the scheduler process (pid 52300). The C′ child (pid 52305) kept running. A STOP file would also have stopped C′.
**Built or changed:**
- `src/hysteresis/run_arm.py`: `PROVENANCE_PATHS` narrowed to the code a run executes (src/hysteresis, scripts/study2, src/runner/costs.py, src/runner/runner.py, src/upstream.py, src/__init__.py, third_party). `configs/` is shared with A06, so the SHA-256 of `configs/caps.yaml` and `configs/prices.yaml` in effect is recorded per run (`config_sha256`). The guard still enforces the caps on disk and fails closed without a `study2` entry.
- `src/hysteresis/scheduler.py`: attempts = max(run directories, launch events in `scheduler.jsonl`), so launches that die early count toward MAX_ATTEMPTS = 3.
- `tests/test_study2_build.py`: `test_failed_launches_count_as_attempts`, in live mode refused under pytest: exactly 3 launches per arm, and no journal.
**Checks performed:** `pytest tests/test_study2_build.py -k "failed_launches or scheduler or counted or live_refused"`: 4 passed.
**Next:** commit, then restart the P8 scheduler with `--reset-attempts` (operator event `attempts_reset` with the reason, added to the append-only `scheduler.jsonl`; launch counts restart after it, so the refused launches of the fixed bug do not exhaust B/A′). It continues: the prefix is complete, C′ runs as an orphan (detected), and B and A′ launch.

## 2026-10-24 12:49–13:20 UTC — Claude Code (Opus 5.5), session A05 — Task 3: P8 live (rep001, all arms); Task 4 (part): D21 → n = 50

**Assignment / authorization:** A05 task 3 (P8 live on one sequence through all arms, cap 5 USD, after the main run finished: the Study 1 main run ended at 12:05 UTC and A04 closed out at `08e2a7e`). Nick's clarification: P8 is pilot data, not reused, no outcome looked at, its cost counts in D21.
**Launch (exact):** `set -a && . ./.env && set +a && PYTHONPATH=. nohup .venv/bin/python -m scripts.study2.launch --group p8 --seqs 1 --workers 5 --backend live --approved-stage study2 > logs/study2_p8.log 2>&1 &` at 12:49:46 UTC, commit `417f2a8`. Restart after the provenance fix at 13:02:31 UTC (commit `a17b809`) with the same command plus `--reset-attempts "<reason>"` (appended to the log).
**Observed (operational only):**
- 5/5 arms complete at 13:13:48 UTC; 702 calls; 699 accepted plus 3 `empty_no_content` (retried by upstream); 0 API errors; 0 rate-limit errors; `response_model` gemini-3.1-flash-lite on all 699 accepted.
- Cost 2.9755 USD: prefix 0.42, A′ 0.50, B 0.63, C′ 1.12, PC 0.29. Cached share of input 0.820 (30.8 M of 37.5 M tokens), higher than the 44% of the A02 pilot and Shi et al.'s ~71%.
- Wall time: prefix 8.8 min, A′ 6.8, B 7.4, C′ 13.4, PC 3.5. Critical path ≈ 19.7 min, plus the 3.7-minute interruption gap.
- Study 2 code paths were clean for every run (`study2_code_dirty` = []). The prefix and C′ ran at `417f2a8`, the branches at `a17b809` (changes in between: provenance scope and launch counting only, no request content), PC under HEAD `8e138ca` (an A06 commit).
**Status-line grep check:** `scripts.study2.analyze --runs results/study2/p8/runs.csv --status-line-only`: PASS, 90 rows, 0 failures, 0 mentions beyond the opening.
**Not looked at:** strict_full, verdicts, messages, rewards, or any outcome in the P8 traces. The PC run completing implies upstream's load-time validation accepted the D22 messages and the rebuilt slot (`partner_control` raises otherwise). That is a code check, not a reading.
**D21 (`scripts.study2.fix_n`, `results/summaries/study2_n.json`):** 2.9755 × 1.15 = 3.4218 USD per sequence. Remaining Study 2 cap 247.02 USD; remaining hard cap 308.27 USD (other project spend 18.76 USD). 50 × 3.42 = 171.09 ≤ 247.02, so **n = 50**, rep001–rep050. Caveat: this is a single-sequence cost estimate. At Shi's p90/median ratio (~1.3), 50 sequences would cost about 194 USD, still within the cap, and the guard fails closed regardless.
**Evidence committed:** `results/study2/p8/` (journals, `study2_meta.json`, `scheduler.jsonl`, `runs.csv`, Bob cache, `run.json.gz`, `run_json_sha256.txt` of the uncompressed records); `results/summaries/study2_p8_monitor.json`; `results/summaries/study2_n.json`. Uncompressed `run.json` stays local (`.gitignore`). One sequence is about 67 MB uncompressed and 20 MB gzipped.
**Changed:** `scripts/study2/prereg_hashes.py` hashes committed blobs at a revision, because A06 holds uncommitted edits to shared files.
**Did not work:** the provenance refusal and relaunch loop (previous entries).
**Open for Nick:** storage of the main run (about 1 GB gzipped for 50 sequences) in git.
**Next:** commit, write the hashes into `PREREGISTRATION_STUDY2.md`, commit, tag `prereg-study2`, push, launch the main run at 8 workers.
