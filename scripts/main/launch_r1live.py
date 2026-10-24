"""R1-live launcher (plan 8.4; D16, D19). Frozen by tag prereg-v1-r1live; launch authorized by Nick
(24 Oct 2026) after the main run has finished, not in parallel with it. Stage cap `r1live` = 10 USD in
configs/caps.yaml.

Items: the 40 of data/derived/prereg/r1live_subset.csv (frozen in prereg-v1), one R1-live run each,
check "R1LIVE", stage "r1live", 4 workers (items round-robin). Driver: src.replay.live_driver.

  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.main.launch_r1live --live --approved-stage r1live \
      --workers 4 > logs/r1live.log 2>&1 &
  .venv/bin/python -m scripts.main.launch_r1live --plan
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.runner.jobs import make_r1live_job

ROOT = Path(__file__).resolve().parents[2]
SUBSET = ROOT / "data" / "derived" / "prereg" / "r1live_subset.csv"
STAGE = "r1live"


def jobs():
    from src.runner.item_lists import main_items
    sub = pd.read_csv(SUBSET).item_id.tolist()
    m = main_items().set_index("item_id").loc[sub].reset_index()
    return [make_r1live_job("R1LIVE", r) for r in m.itertuples()]


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="R1-live launcher")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    js = jobs()
    report_plan("R1-live", js)
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    rdir, qdir = DIRS[mode]
    return run_parallel("scripts.main.launch_r1live:jobs", max(1, a.workers), stage=STAGE, mode=mode,
                        results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=2026)


if __name__ == "__main__":
    main()
