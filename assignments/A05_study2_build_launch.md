# Assignment A05 — Study 2: build, P8, preregistration, launch
Issued by Nick, 24 October 2026. Governing design: PROJECT_PLAN.md §9 (frozen), plus the decisions below. Read docs/study2_implementation_plan.md first.

## Coordination with the running A04 session (important)
Another Claude Code session is finishing A04 (main run, R1-live) in this same working tree. Until A04's final report is committed and pushed (check git log and devlog/03_core_experiment.md):
- touch only your own paths: src/hysteresis/, tests for it, scripts/study2/, docs/study2_*, PREREGISTRATION_STUDY2.md, devlog/04_hysteresis.md;
- never use git add -A or git add .; stage explicit paths only; before pushing, git pull --rebase of your own unpushed commits is allowed (never rewrite pushed history);
- do not edit docs/deviations.md, configs/caps.yaml, DEVLOG_INDEX.md, or other devlog blocks yet; queue those edits and apply them after A04 is done;
- make no live API calls while the main run is still running.

## Decisions by Nick (record as D20–D23 in docs/deviations.md once A04 is done)
- D20 Budget: total hard cap raised from 250 to 330 USD; Study 2 stage cap 250 USD including P8. Runners fail closed.
- D21 Number of pairs, fixed by cost only, before launch: after P8, use the measured cost per sequence (including the cache share actually observed) plus a 15% reserve; take the largest n of 50, 40, 30 that fits the remaining Study 2 cap. Sequences are rep001 onward in order (plan §9.1, extended to 50). If 30 does not fit, Study 2 is dropped and reported as a preregistered future study. No look at any outcome before n is fixed.
- D22 Partner control message mapping: the channel is unlimited, so scripted Bob sends his complete raw log verbatim in round 1 as one message with the framing "RAW LOG PART 1/1:"; in rounds 2–5 he sends one fixed neutral sentence ("I have sent my complete raw log above."). Only if a technical message limit exists, split deterministically across rounds 1..n with "RAW LOG PART i/n:" and record it.
- D23 Parallelism: as many workers as rate limits allow without errors; ramp from 8 to 16 to 32 only while 429 errors stay at zero; a rising error rate means stop and look (plan §23.3). Parallelism never changes a run's content.

## Tasks
1. Build status line, branching (--resume-from with --throttle-spans), arms A′, B, C′, and the partner control, using Shi et al.'s own code (plan §§9.1, 23.1). Use parallel builders where independent. Tests and a full dry run without API calls.
2. Write the Study 2 analysis code (plan §§9.2, 9.3: paired t-test and sequence bootstrap on strict_full episodes 6–8, B − C′; secondary outcomes; status-line grep check) and test it on simulated data.
3. After the main run has finished: P8 live on one sequence through all arms (cap 5 USD). Measure cost per sequence, cache share, wall time, 429s. Check by grep that the status line appears from episode 6 in every arm and nowhere before.
4. Apply D21 and fix n. Write PREREGISTRATION_STUDY2.md (plan §9 as frozen, D20–D23, n, sequence list, analysis code hash), commit, tag prereg-study2, push.
5. Launch authorized if P8 passed and n ≥ 30: prefixes and independent arms in parallel; B before partner control within each sequence; resumable runner in tmux or nohup with logs; monitor errors, response_model, cost. Read the first complete sequence by hand before scaling up.
6. Report: P8 result, n and its derivation, launch time, projected finish, spend. No outcome statistics before the run is complete.
