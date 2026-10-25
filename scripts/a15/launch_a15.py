"""A15 launcher: history decomposition R3t ("earlier work only") and R3o ("earlier outcomes only") on the 50 D25
omission items (D38; stage "a15", cap 6 USD).

Cells (check "HIST"; Gemini 3.1 Flash-Lite, Shi et al.'s parameters as in the main run), per item:
  R3t, R3o x {omission, correct} x draws {1, 2}  -> 8 calls per item, 400 in total.
  Contexts: src.replay.r3_history.build with bob_r1_content = the item file's omission content (version "omission")
  or None = Bob's original message (version "correct").
  Baselines R1-om, R0' (a06 / main run), R2, R3 (A13) are reused, never rerun.
Order: numpy default_rng(2026): permutation of the items, then one permutation of each item's 8 cells; all calls of an
item are adjacent (plan 8.5). Call IDs "a15:HIST:<item>:<variant>:<version>:<draw>".
Stop rules: response_model change (shared runner, check of 297c244); the A10 stop guard (src.replay.a10.guarded_verdict:
any 429 containing "spending cap"; more than 10 quota 429s within 5 minutes) with guard directory logs/a15_guard/<mode>/
(a STOP file there makes the launcher refuse to start).

  .venv/bin/python -m scripts.a15.launch_a15 [--first] --plan
  .venv/bin/python -m scripts.a15.launch_a15 [--first] --workers 4          # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a15.launch_a15 [--first] --live --approved-stage a15 \
      --workers 4 > logs/a15.log 2>&1 &
--first: the first 3 items of the order, complete (24 calls), read by hand before continuing (plan 23.3).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from src.replay import a10, r3_history
from src.replay.r5_a13 import omission_items
from src.replay.variants import load_item
from src.runner.estimates import input_tokens
from src.runner.jobs import MODEL
from src.runner.runner import Job

STAGE = "a15"
CHECK = "HIST"
SEED = 2026
FIRST_ITEMS = 3
VARIANTS = r3_history.VARIANTS
VERSIONS = ("omission", "correct")
CELLS = [(v, ver, d) for v in VARIANTS for ver in VERSIONS for d in (1, 2)]


def build_messages(o: dict, variant: str, version: str) -> list:
    content = o["bob_r1_content"] if version == "omission" else None
    return r3_history.build(load_item(o["trace"], int(o["ep_index"])), variant, bob_r1_content=content)


def _job(o: dict, variant: str, version: str, draw: int) -> Job:
    item = o["item_id"]
    return Job(check=CHECK, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: build_messages(o, variant, version),
               est_input_tokens=input_tokens(item, "R3"), model=MODEL, verdict_fn=a10.verdict_fn())


def jobs() -> list[Job]:
    rng = np.random.default_rng(SEED)
    om = omission_items()
    out = []
    for i in rng.permutation(len(om)):
        js = [_job(om[i], *c) for c in CELLS]
        out += [js[k] for k in rng.permutation(len(js))]
    return out


def first_jobs() -> list[Job]:
    js = jobs()
    keep = list(dict.fromkeys(j.item_id for j in js))[:FIRST_ITEMS]
    return [j for j in js if j.item_id in keep]


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A15 launcher (R3t, R3o)")
    ap.add_argument("--first", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    name = "first_jobs" if a.first else "jobs"
    js = globals()[name]()
    for v in VARIANTS:
        report_plan(f"A15 {v}{' stage 1' if a.first else ''}", [j for j in js if j.variant == v])
    report_plan(f"A15 total{' stage 1' if a.first else ''}", js)
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a15_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a15: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # the A10 guard's directory variable; inherited by the workers
    rdir, qdir = DIRS[mode]
    stats = run_parallel(f"scripts.a15.launch_a15:{name}", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a15: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
