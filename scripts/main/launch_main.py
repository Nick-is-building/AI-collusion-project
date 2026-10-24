"""Main-run launcher (A04 task 3; PROJECT_PLAN.md sections 8.5, 12, 13, 23.3).

Job list: src.runner.jobs.main_run_jobs (2,330 calls, seeded order, frozen in prereg-v1 as
data/derived/prereg/main_run_call_ids.txt). Stage "main", cap configs/caps.yaml stages.main (40 USD,
A04), hard cap 250 USD; 4 worker processes (src.runner.parallel: items round-robin, caps split
fail-closed); append-only JSONL in results/raw/, resumable by call ID.

Two launch stages (A04 task 3):
  --first    the first 5 main items, the first 5 natural-error items and the first 2 fidelity cases of
             the frozen order, complete (all their calls; item blocks stay together, plan 8.5). That gives
             >= 5 complete calls for every variant (R0, R0p, R1, R2, R3, R4, R4n, R5, R6, N1, N4, FR0),
             which are read by hand before scaling (plan 23.3).
  (default)  the full list. Calls already logged (stage 1) are skipped by call ID, so stage 1 and the
             full run form one dataset with one call ID set.

  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.main.launch_main [--first] --live --approved-stage main \
      --workers 4 > logs/main_<stage>.log 2>&1 &
  .venv/bin/python -m scripts.main.launch_main [--first] --plan      # projection only
  .venv/bin/python -m scripts.main.launch_main [--first]             # mock (no network), logs/mock_runs/
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.runner.jobs import main_run_jobs

ROOT = Path(__file__).resolve().parents[2]
STAGE = "main"
SEED = 2026
FIRST = {"main": 5, "natural": 5, "fidelity": 2}
GROUP = {"N1": "natural", "N4": "natural", "FR0": "fidelity"}
DIRS = {"mock": (ROOT / "logs" / "mock_runs" / "raw", ROOT / "logs" / "mock_runs" / "requests"),
        "live": (ROOT / "results" / "raw", ROOT / "results" / "requests")}


def first_jobs():
    """Stage 1: complete item blocks at the head of each part of the frozen order."""
    jobs = main_run_jobs()
    seen = {g: [] for g in FIRST}
    out = []
    for j in jobs:
        g = GROUP.get(j.variant, "main")
        key = (j.item_id, j.judge)
        if key not in seen[g]:
            if len(seen[g]) >= FIRST[g]:
                continue
            seen[g].append(key)
        out.append(j)
    return out


def main(argv=None):
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="Main-run launcher (A04 task 3)")
    ap.add_argument("--first", action="store_true", help="stage 1: >= 5 complete calls per variant")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    factory = "scripts.main.launch_main:first_jobs" if args.first else "src.runner.jobs:main_run_jobs"
    jobs = first_jobs() if args.first else main_run_jobs()
    report_plan(f"main run{' stage 1' if args.first else ''}", jobs)
    if args.plan:
        return None
    mode = "live" if args.live else "mock"
    rdir, qdir = DIRS[mode]
    stats = run_parallel(factory, max(1, args.workers), stage=STAGE, mode=mode, results_dir=rdir, requests_dir=qdir,
                         approved_stage=args.approved_stage, seed=SEED)
    for s in stats:
        print(f"main: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
