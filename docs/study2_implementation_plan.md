# Study 2 (hysteresis): implementation plan (A04 task 5, as corrected by Nick)

**Status.** Plan only, 24 October 2026, about 11:25 UTC. Nothing is built and no call was made (Nick: "No building and no calls yet"). The design is `PROJECT_PLAN.md` §9; this file plans how to build and run it. It changes no design point. Open design questions are marked **Nick**.

**Sources.**
- Upstream reading and trace measurements: delegated to a read-only subagent; report in `scratch/a04/study2_findings.md` (local); helper `scratch/a04/study2_trace_stats.py`.
- Spot-checked by the main session:
  - `--resume-from` exists in `experiments/runner.py` (line 284), not in `cli.py`;
  - the helper reproduces 65.27 USD with cache and 163.99 USD without for the 50 unconstrained Flash-Lite traces.
- Our own timing: P7 and the A04 main run (`devlog/02_pilot.md`, `devlog/03_core_experiment.md`).

## 1. Build steps and time (estimates)

| # | Step | What | Exists upstream | To write | Est. time |
|---|---|---|---|---|---|
| 1 | Run wrapper | Launch one upstream run (`experiments.runner`) per arm and sequence, from a dedicated copy of the upstream tree. The working directory matters: upstream writes temporary test files under `cwd/results/tmp_tests`, and a symlinked tree breaks prompt paths. The wrapper checks the settings resume does not check: model, sampling, throttle spans. It enforces a fail-closed cost cap from `llm_usage_journal.jsonl`, logs run IDs, and hashes `run.json`. | runner, resume, per-run journals | wrapper, cap, checks, provenance | 1.5 h |
| 2 | Prefix (eps 1–5) | There is no "stop after 5 episodes" option. A 5-pair manifest fails resume's manifest-path check, so the wrapper calls `_run_selected_episodes` with the first 5 pairs of the unchanged 10-pair manifest. | `_run_selected_episodes` | thin wrapper + test | 0.5 h |
| 3 | Branching | `--resume-from <prefix run.json>` with `--throttle-spans` (A′: all throttled; B and partner control: `throttled:5,no-throttle:*`). Resume reads the prefix without modifying it and writes a new output directory, so one prefix can seed A′, B, and the partner control at the same time. Each branch's `run.json` re-sums the copied prefix usage, so costs come from the per-run journals only. | resume | branch launcher, double-count guard | 1 h |
| 4 | Status line | From episode 6, one neutral line in every arm's communication opening (plan §9.1 texts). Patch point: wrap `episode_runner._prepare_pair` and append the line to the peer `judging_prompt` when `episode_index >= 5`, with the text chosen from `config.throttled`. No submodule edit. The line is saved per episode in the results, so plan §23.3's grep check works. | – | patch + test (grep from ep. 6, nowhere before) | 1 h |
| 5 | Partner control | Bob is scripted from episode 6 from the B run of the same sequence, Alice is live (§9.1). Upstream has a scripted-Bob mode (`controlled.py`): a cached task state, five prewritten messages of at most 200 characters, and one fixed verdict per run. `record_peer.py` records Bob live with LLM calls, so it does not fit. To write: (a) a converter from B's `run.json` (eps 6–10: Bob's answers, raw log, events) to the cache format, with no calls; (b) a message mode that splits Bob's complete raw log into "RAW LOG PART i/n:" messages without the 5 × 200 character check; (c) a per-episode verdict replay instead of the single fixed verdict (`episode_runner.py` 791–797); (d) relaxed resume checks for this arm only, since upstream refuses to switch a live Bob to a scripted one (`runner.py` 497–519, 528–533). | partial | (a)–(d) + tests | 2.5–3 h |
| 6 | Scheduler | One process per run. The prefix and C′ start at once for all sequences; A′ and B start when their prefix ends; the partner control starts when its B ends. Critical-path runs (prefix → B → partner control) take priority. The scheduler is resumable at run level (upstream resumes only at episode boundaries), keeps one run ID per launch, and an operational monitor tracks errors, `response_model`, and cost. | – | scheduler + monitor | 1 h |
| 7 | Tests and dry run | Upstream `--dry-run` plus a mock model: branch from a mock prefix, status line present from episode 6 only, partner messages split correctly, verdict replay, caps, resume after a kill. | dry-run | tests | 1 h |

Total: about 8.5–9 h of build and test time if done sequentially by one session. Steps 4 and 5 are independent of 1–3 and can be built in parallel, by subagents in worktrees, which brings it to about 5–6 h wall time.

**Nick (open design questions, needed before step 5):**
1. Plan §9.1 does not fix how the n "RAW LOG PART i/n" parts map onto the 5 rounds, nor what Bob sends in rounds left over when n < 5. Bob's unconstrained round-1 messages in the published traces were up to about 15,000 characters, so the whole log usually fits in one message. Proposal: n = 1 whenever the log fits upstream's unconstrained message (that is, the whole log in round 1), and in rounds 2–5 a fixed acknowledgement text.
2. Plan §9.1 also does not say whether the partner control's Bob verdict is replayed from B even when Alice's live answer differs from her B answer. The plan accepts this ("Bob's replayed verdict can be wrong for Alice's live answer"), so: replay as in the plan.
3. The constrained (200-character) Flash-Lite traces are not downloaded (`traces/main/...` is absent), so the constrained arms are costed with the unconstrained figures as an upper bound.

## 2. Calls, cost, wall time

**Per-run measurements** (50 unconstrained Flash-Lite traces, observed; the repricing equals the recorded `cost_usd`):

| Unit | Calls (median) | USD with cache (mean) | USD without cache (mean) |
|---|---:|---:|---:|
| Episodes 1–5 | 115 | 0.46 | 0.93 |
| Episodes 6–10 | 115 | 0.85 | 2.35 |
| Full 10 episodes | 230 | 1.31 | 3.28 |

- Shi et al.'s cache share is about 71% of input. "With cache" assumes our runs reach the same share; unverified.
- Every call within a run is sequential (Alice then Bob; about 23 calls per episode).

**Per sequence, all arms** (constrained arms bounded above by the unconstrained figures; the partner control counts Alice's calls only, about half of B, which is inferred):

| Arm | Starts after | Calls | USD with cache | USD without cache |
|---|---|---:|---:|---:|
| Prefix (eps 1–5, constrained) | – | 115 | ≤ 0.46 | ≤ 0.93 |
| A′ (eps 6–10, constrained) | prefix | 115 | ≤ 0.85 | ≤ 2.35 |
| B (eps 6–10, unconstrained) | prefix | 115 | 0.85 | 2.35 |
| C′ (eps 1–10, unconstrained) | – | 230 | 1.31 | 3.28 |
| Partner control (eps 6–10, Alice live) | B | ~58 | ~0.42 | ~1.18 |
| **Sequence total** | | **~633** | **≤ 3.9** | **≤ 10.1** |

**Totals:**

| Scope | Calls | USD with cache (≤) | USD without cache (≤), plan §12 rule |
|---|---:|---:|---:|
| P8 (1 sequence: prefix, B with status line, resume check; plus one partner-control episode as a smoke test) | ~245 | ~1.4 | ~3.4 |
| 40 pairs | ~25,300 | ~156 | ~404 |
| 50 pairs (all of Shi et al.'s sequences) | ~31,650 | ~195 | ~505 |

- **Budget conflict (Nick):** plan §12 lists Study 2 at 115–150 USD "without cache savings". The measured no-cache figure for 40 pairs is about 404 USD, above the 250 USD hard cap on its own. Only the with-cache figure (about 156 USD) is near the plan's range.
- The runner's fail-closed ledger counts billed tokens (cached tokens at the cached price), so actual spend follows the with-cache figure if caching occurs. Our A02 pilot saw 44% cached input. A per-stage cap must be set by Nick before launch.
- Project spend so far: pilot about 1.53 USD; main run about 15 USD projected from the running rate (operational figure).

**Wall time.**
- Basis: about 5 s per API request (observed: P7 live communication and verdict calls 3.5–5.2 s; main run median 5.4 s per request). Range 3.5–6 s.
- Critical path per sequence: prefix → B → partner control = 115 + 115 + 58 ≈ 288 sequential calls, so **about 24 min** (17–29 min). No parallelism shortens this.
- Total work: 40 pairs ≈ 35 worker-hours; 50 pairs ≈ 44 worker-hours.
- Wall time ≈ max(critical path, work / workers). Runs are scheduled with the critical path first; run lengths are 58–230 calls, so the tail adds at most about 20 min.

| Workers (parallel runs) | 40 pairs | 50 pairs | Needed throughput (input ≈ 55k tokens per call) |
|---:|---:|---:|---|
| 4 | ~8.8 h | ~11.0 h | ~48 RPM, ~2.6 M TPM |
| 8 | ~4.4 h | ~5.5 h | ~96 RPM, ~5.3 M TPM |
| 16 | ~2.2 h | ~2.8 h | ~190 RPM, ~10.6 M TPM |
| 32 | ~1.1 h | ~1.4 h | ~385 RPM, ~21 M TPM |

P8: about 230 sequential calls (≈ 20 min) plus about 12 partner-control calls; about 30–40 min including the checks.

## 3. Gemini rate limits for this key

- **Not readable without a call or a login.** Google's rate-limit page states that "Rate limits are applied per project, not per API key", that they are "tied to the project's usage tier", and that you can "View your active rate limits in AI Studio".
- The public page has no RPM/TPM/RPD table for Gemini 3.1 Flash-Lite, only Batch API enqueued-token limits (Tier 1: 10 M; Tier 2: 500 M; Tier 3: 1,000 M). Tier rules: Tier 1 = linked billing account; Tier 2 = $100 paid + 3 days; Tier 3 = $1,000 paid + 30 days.
- Source: https://ai.google.dev/gemini-api/docs/rate-limits (read through a tool summary, 24 Oct 2026, ~11:20 UTC).
- **Observed:** main run at 4 workers, about 39 calls/min and roughly 1.6 M input TPM, with 0 rate-limit errors.
- **Nick:** read the project's limits in AI Studio. That decides whether 8, 16 or 32 workers are usable. Without it, 8 workers is the cautious next step, with a stop rule on rising 429s (plan §23.3).

## 4. Earliest realistic launch

From now (Saturday ~11:30 UTC):
- A04 closes after the main run ends (projected ~12:05 UTC) and the report.
- Build of steps 1–7: ~12:30 → ~18:00–19:00 UTC sequentially, or ~17:30 UTC with parallel builders. It needs answers to the three Nick questions before step 5, about 14:00 UTC at the latest.
- P8: ~19:00–19:45 UTC.
- **Earliest realistic full launch: Saturday about 20:00 UTC (22:00 Berlin).**
- At 8 workers, 40 pairs end about 00:30 UTC Sunday and 50 pairs about 01:30 UTC. At 4 workers: about 05:00 / 07:00 UTC.
- Plan §9 gates: P8 on Saturday evening holds. "≥ 30 pairs by Sunday 18:00 Berlin" (16:00 UTC) holds with margin. "Partner control only for sequences whose B finished by Sunday 09:00 Berlin" (07:00 UTC) holds at ≥ 8 workers, and is borderline at 4 workers with 50 pairs.
- R1-live (40 items × 10 calls ≈ 400 calls, ~10 min at 4 workers) can run before or alongside, if authorized.
