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

## 2026-10-24 13:15–13:20 UTC — Claude Code (Opus 5.5), session A05 — Task 4 done (prereg-study2); Task 5: main run launched

**Assignment / authorization:** A05 task 4 (preregistration, tag) and task 5 (launch authorized if P8 passed and n ≥ 30: P8 passed, n = 50).
**Preregistration:** `PREREGISTRATION_STUDY2.md` final at `c6ab3de`, tag `prereg-study2` (annotated, pushed; tag object `64dd86b`). The frozen-file hashes are computed at `62662d4` with `scripts/study2/prereg_hashes.py`. Nothing in Study 2 was computed or read before the tag except P8's operational figures and the status-line PASS.
**Launch (exact):** `set -a && . ./.env && set +a && PYTHONPATH=. nohup .venv/bin/python -m scripts.study2.launch --group main --seqs 1-50 --workers 8 --backend live --approved-stage study2 > logs/study2_main.log 2>&1 &` at 13:16:50 UTC, HEAD `c6ab3de`, Study 2 code paths clean. Runs under `results/study2/main/`, per-run logs `logs/study2/main/`.
**Observed in the first 60 s:** 8 launches (prefixes rep001–rep008), 87 calls, all accepted, 0 errors, 0 rate-limit errors, `response_model` constant.
**Scheduling note (inferred from the frozen priority B, PC, prefix, C′, A′):** all 50 prefixes launch before any C′ or A′. The first complete sequence will therefore arrive after roughly 60–75 min, not about 20 min. Workers stay at 8 until that sequence has been read by hand (A05 task 5). I did not change the frozen scheduler (it would be a post-tag change). Cost: wall time only, not content.
**Built:** `scripts/study2/watch.py`: operational watcher; it exits on errors, 429s, a model change, STOP, a failed attempt, scheduler end, or completion of a given sequence. It reads only what the monitor reads.
**Next:** hand-read sequence 1 (operational: contexts, messages and status line look as designed; no rate computed), then ramp to 16 and 32 workers only while 429s stay at zero (D23).

## 2026-10-24 13:25–13:35 UTC — Claude Code (Opus 5.5), session A05 — Nick's answers recorded (D27); export of the committed record

**Assignment / authorization:** Nick's answers in the session (verbatim in `docs/deviations.md` D27): H7 confirmed as preregistered; do not commit the 1 GB raw run but derived per-call tables, file hashes and a manifest (HF dataset later, separate assignment); quoted status lines acceptable, with their frequency reported.
**Built or changed:**
- `docs/deviations.md` D27.
- `PREREGISTRATION_STUDY2.md` §10, a post-tag record. The tag keeps the original text.
- `scripts/study2/export.py`: writes `manifest.csv`, `files_sha256.txt`, `calls.csv.gz` per group, with operational fields only. Tested on the mock interrupt-check output: 11 runs, 1,005 calls, 44 files hashed.
- `.gitignore`: main-run journals, Bob caches and any `run.json.gz` stay local.
**State:** the main run continues at 8 workers. The export runs after the run completes (and can be rerun at any time).
**Next:** hand-read sequence 1, then ramp up.

## 2026-10-24 20:55–21:20 UTC — Claude Code (Opus 5.5), diagnosis session — Study 2 main run: cause of the 32 failed C′ arms (diagnosis only, no call, no outcome)

**Assignment / authorization:** Nick (session prompt, about 21:00 UTC): diagnose only. No reruns, no API calls, and no computing or viewing of any Study 2 outcome (strict_full, verdicts). Find the exact cause of the 32 failures, check whether successful arms are affected, report spend, give options (a) and (b) with cost and wall time, log, commit, push, stop. Context from Nick: the supervising Claude Code session lost its credit at about 15:28 UTC and could not act.
**Built or changed:**
- `scripts/study2/diagnose_failures.py`: reads only `scheduler.jsonl`, `study2_meta.json`, usage journals, the error lines of the per-run logs, and the project ledger. It reads no message, verdict or strict_full.
- `results/summaries/study2_main_failure_diagnosis.json`: its output.
**Checks performed:** `PYTHONPATH=. .venv/bin/python -m scripts.study2.diagnose_failures --group main --json results/summaries/study2_main_failure_diagnosis.json`, plus ad-hoc greps of `logs/study2/main/*.log` for error lines, and per-arm cost and duration taken from the journals and metadata. No process was running (`ps`). The scheduler ended at 20:53:56 UTC: done 218/250, failed = C′ of rep014–rep045, `stopped: false`.
**Observed — cause:**
- Every one of the 96 failed C′ attempts (32 arms × 3 launches) ends in `LLMRetryLimitExceededError` after 21 API attempts. The error is a Gemini HTTP 429 `RESOURCE_EXHAUSTED`: "Your project has exceeded its monthly spending cap. Please go to AI Studio at https://ai.studio/spend …".
- This is Google AI Studio's project spend cap, not our guard: no `Study2Stop`, no STOP file, our caps far from reached.
- No call was accepted project-wide from **15:49:30 to 19:53:47 UTC** (the only gap > 5 min in the journals). The cap was evidently raised or lifted at about 19:53 UTC. That is inferred from the journals; who changed it is not visible here.
- Spend at the moment the cap was hit, by our ledger: Study 2 main 73.51 + P8 2.98 + other stages 26.63 ≈ 103 USD. The cap value itself is not visible from the repository.
**Observed — mechanism (why only C′ 14–45):**
- Upstream classifies the 429 as `transient_rate_limit` and retries 20 times with backoff, so each attempt took about 18 min before failing. The scheduler then relaunched; after 3 launches the arm was final-failed (MAX_ATTEMPTS = 3).
- At 15:49 all prefixes, B and PC were done (last PC exit 15:34:35). C′ arms 1–13 had finished at 15:27–15:49:16. Under the frozen priority (B, PC, prefix, C′, A′), the 8 worker slots were filled with C′ 14–45 in successive batches. Each batch burned its 3 × ~18 min during the cap window: 14–21 at 15:42–16:45, 22–29 to 17:41, 30–37 to 18:36, 38–45 to 19:32.
- C′ 46–50 attempt 1 (19:29–19:49) and A′ 1–3 attempt 1 (19:32–19:50) also failed on the cap. Their attempt 2 started at about 19:48–19:50 and succeeded once the cap was lifted.
- Partial progress before the cap: C′ rep014 4 episodes, rep015 3, rep016 2, rep017 1 (attempt 1; attempts 2–3 resumed and added nothing); rep018–rep045 0 episodes. Cost of all failed C′ attempts 0.876 USD.
- Which arms failed was set by queue position, not by any arm or sequence content. The 15:28 credit loss of the supervising session left nobody to stop the scheduler after the first spend-cap error (plan §23.3: "a rising error rate means stop and look").
**Observed — are successful arms affected:**
- All 218 complete arms: `response_model` gemini-3.1-flash-lite on all 27,057 accepted calls; Study 2 code paths clean in every counted run (`study2_code_dirty` empty).
  - Between `prereg-study2` (`c6ab3de`) and HEAD `86c47aa`, the only changes in the provenance paths are two new, non-executed scripts: `scripts/study2/export.py` and `watch.py`.
  - `configs/caps.yaml` changed three times (A07/A08 stage caps), but `hard_cap_usd` 330 and `stages.study2` 250 are identical in all versions.
- 28 transient 429 "You exceeded your current quota" errors (a rate quota; the metric name is truncated in upstream's log line). Bursts at 15:27:46–15:28:03, 15:41:53–15:44:02 and 15:49:25, in C′ 2–13 and in B rep049/rep050 and PC rep048. All were retried successfully by upstream. A retry resends the same request, so content is unaffected (preregistered error handling, PREREGISTRATION_STUDY2 §6). They do mean the D23 condition for ramping above 8 workers ("429s stay at zero") is not met.
- 8 counted runs started before the lift (A′ 1–3, C′ 46–50 attempt 2) and absorbed up to 6 spend-cap retries on their first call before proceeding. Same request, no content effect.
  - A′ 1–3 attempt 2 resumed from the **prefix**: attempt 1 had only the 5 prefix episodes, and the resume floor is 5.
  - C′ 46–50 attempt 2 ran **fresh**: attempt 1 had 0 episodes.
  - So no counted run is stitched from a pre-cap and a post-cap process.
- A′ rep004: attempt 1 (launched 19:59:59, after the lift) failed differently. It got 21 `content_filter` responses on one call (20:01–20:19). Attempt 2 restarted from the prefix and completed. This is a technical resample of a secondary arm under the preregistered retry rule; no outcome was involved.
- Timing (operational, not an outcome): C′ ran 1.5–2 h after B for rep001–013 (frozen priority) and about 4.5 h after B for rep046–050 (cap window). B and C′ of a sequence were therefore never simultaneous, even in complete sequences.
**Spend (our ledger, `JournalLedger` / `Ledger`, list prices incl. cache):**
- Study 2 main 105.24 USD (incl. 0.88 in failed attempts) + P8 2.98 = **108.21 USD of the 250 cap** (141.79 left).
- Other stages (`results/raw`) 26.63 USD.
- **Project total 134.84 USD of the 330 hard cap** (195.16 left).
- Google's own billing figure is not visible here.
**Options (estimates from the 218 complete arms; 8 workers, because quota 429s occurred, D23):**
- **(a) Rerun only C′ 14–45 (32 arms):**
  - cost 32 × 1.075 = 34.4 USD (upper, at the max arm 1.44: 46.1);
  - wall time: C′ mean 15.7 min, max 22.7 → 4 batches ≈ 65–90 min.
  - Needs `--reset-attempts`. The frozen scheduler would **resume** rep014–017 from their partial pre-cap episodes. A fresh C′ for those four would need a decision, plus a flag or code change.
- **(b) Rerun all arms of rep014–rep045 (plan §9.2; PREREGISTRATION_STUDY2 §6):**
  - cost 32 × 2.771 = 88.7 USD per complete sequence (upper, at the max 3.45: 110.3);
  - wall time: 41 worker-min per sequence → ≈ 2.7 h at 8 workers, plus a ~20 min critical-path tail ≈ 3 h.
  - The existing complete prefix/A′/B/PC of those 32 sequences would be superseded. They need a new run group or directory so they are kept as evidence and never analysed (not looked at).
- Either option fits both caps. Either needs AI Studio spend-cap headroom of at least the upper figure first, or it fails the same way.
**Assessment (inferred):** (b) preserves the preregistered design better.
- It is the procedure the plan (§9.2: "all arms of that sequence are rerun to keep the pairing") and the preregistration (§6) name for exactly this case.
- Plan §9.1 uses fresh prefixes "so that B and C′ come from the same model deployment". Under (a), the 32 C′ arms would run ≥ 6 h after their B, and two thirds of the sample (32/50 pairs) would carry a systematic B-early / C′-late split.
- Under (b), each sequence's arms run together in one window, with the same within-sequence lag as rep001–013.
- (a) is cheaper by about 54 USD and 1.5–2 h. The failure is outcome-independent (provider billing), so (a) introduces no selection bias, only a time confound in the pairing. If chosen, it is a deviation to record.
**Did not work / not determined:** the AI Studio cap value and who lifted it; the full quota-metric name of the transient 429s (truncated by upstream logging).
**Not looked at:** strict_full, verdicts, messages, rewards, or any outcome. `episodes` counts come from `study2_meta.json`.
**State / limitations:** `results/study2/main/` is still untracked. The D27 export (`scripts/study2/export.py`) has not been run, since the run is incomplete. The guard does not treat a spend-cap 429 as fail-closed. A possible fix (not made): STOP on "spending cap" in the 429 text.
**Next (proposal, not authorized):** Nick chooses (a) or (b), checks the AI Studio cap, and decides on fresh vs. resumed C′ for rep014–017 if (a).
**Cross-references:** plan §§9.1, 9.2, 23.3; `PREREGISTRATION_STUDY2.md` §6; `docs/deviations.md` D20, D23, D27.

## 2026-10-25 00:00–00:30 UTC — Claude Code (Opus 5.5), session A05b — Task 1: D35, superseding move, stop watcher, sensitivities (no API call, no outcome)

**Assignment / authorization:** `assignments/A05b_study2_relaunch.md` (Nick, 25 October 2026, verbatim; commit `32006b0`): option (a), rerun only C′ of rep014–045, fresh. Nick confirms at least 100 USD of AI Studio spend-cap headroom above current spend.
**Session start:** read CLAUDE.md, DEVLOG_INDEX.md, PROJECT_PLAN.md (complete), this block (complete), PREREGISTRATION_STUDY2.md, docs/deviations.md (D20–D31 and the D17 correction), A05. No process was running. `results/study2/main/` untracked as the diagnosis entry states.
**Concurrent session:** an A10 session (Study 1 incentive/peer-signal arms, stage `a10`) committed D32–D34 (`8d84bbd`) during this work and holds uncommitted `configs/caps.yaml`, `scripts/a10/`, `src/replay/a10.py`. None is touched or staged here. Hence this decision is **D35**, and the relaunch uses 6 workers (A05b rule while another session runs live calls).
**Built or changed:**
- `docs/deviations.md` D35 (decision verbatim, implementation notes).
- `scripts/study2/supersede.py`: the move (see D35). `scripts/study2/stop_watch.py`: fail-closed watcher (rules in D35). `src/hysteresis/scheduler.py` + `scripts/study2/launch.py`: `--require-stop-watch` (no launch while the watcher is dead; event `stop_watch_missing`). `src/hysteresis/run_arm.py`: records `stop_watch` (rules, pid, state, alive at launch) in `study2_meta.json`.
- `src/hysteresis/sensitivity_a05b.py`, `scripts/study2/analyze_a05b.py`: the three sensitivities (frozen `analysis.py` unchanged and reused). Same refusal rule as `analyze.py`.
- `tests/test_study2_a05b.py` (11 tests, synthetic), `scripts/study2/a05b_mock_check.sh` (mock end-to-end check). `.gitignore`: D27 storage rule extended to `main_superseded`.
**Checks performed:**
- `pytest tests/test_study2_a05b.py tests/test_study2_build.py tests/test_study2_partner_control.py tests/test_study2_analysis.py`: 61 passed (234 s).
- `bash scripts/study2/a05b_mock_check.sh` (mock, no API call; output under `scratch/s2a05b/`): mock run of seqs 3–4 with C′ seq 3 killed at episode 2 and resumed; move of C′ seqs 3–4 (3 dirs); watcher started; relaunch with `--reset-attempts --require-stop-watch`, scheduler and new C′ seq 3 child killed again at episode 2, restart. Result: new C′ seq 3 attempt 1 fresh (no resume source), attempt 2 resumed from the new attempt in group `dry` (not from the superseded one), complete 10 episodes; C′ seq 4 fresh, complete; after the reset only the 2 C′ arms were launched (3 launches); every new run records `stop_watch`; watcher ended with the scheduler; no STOP file.
- Real move: `supersede --group main --to-group main_superseded --seqs 14-45 --arm Cprime --reason "A05b (Nick, 25 Oct 2026): C′ rep014–045 superseded after AI Studio spend-cap 429 failures; rerun fresh (D35)"` at 00:22:37 UTC. 96 run directories (32 arms × 3 attempts, 0 complete) moved; SHA-256 of all 288 files identical before and after (lists in `scratch/a05b_*_sha.txt`, local). C′ directories of rep014–045 now empty. Event `superseded_moved` appended to `results/study2/main/scheduler.jsonl`.
- `launch --group main --seqs 14-45 --plan`: 32 C′ ready; prefix, A′, B, PC complete for all 32 sequences.
**Did not work:** none observed.
**Not looked at:** no outcome; only metadata, journals' error fields, file hashes.
**State / limitations:** the watcher counts 429s from usage journals (timestamped); the per-run log lines are used only for the "spending cap" text. If the watcher stops the run, the interrupted C′ arms will have partial episodes; resuming them is a decision for Nick (not automated).
**Next:** commit, push, start the watcher, relaunch (task 2).
**Cross-references:** D35; `PREREGISTRATION_STUDY2.md` §6; plan §§9.2, 23.3; diagnosis entry above.
