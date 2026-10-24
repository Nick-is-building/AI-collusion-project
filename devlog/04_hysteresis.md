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
