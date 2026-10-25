"""A13 launcher: omission-version context ladder R2, R3, R4n, R5 on the 50 D25 omission items (D36; stage "a13",
cap 8 USD).

Cells (check "LADDER"; Gemini 3.1 Flash-Lite, Shi et al.'s parameters as in the main run), per item:
  R2, R3, R4n, R5 x {omission, correct} x draws {1, 2}  -> 16 calls per item, 800 in total.
  Contexts: src.replay.variants.build (R2, R3, R4n) and src.replay.r5.build_r5 (R5), exactly as in the main run,
  with bob_r1_content = the item file's omission content (version "omission") or None = Bob's original message
  (version "correct").
  R5 fillers: src.replay.r5_a13.lookup (omission rows and the 28 new correct rows from
  data/derived/r5_fillers_a13.csv; the 22 main-list correct rows from the prereg-v1 data/derived/r5_fillers.csv).
  The builder fails closed (KeyError, no call) if an item-version has no matched filler.
  Baselines R1-om, R4-om (a06), R0' and R4-correct (main run / a06) are reused, not rerun.
Order: numpy default_rng(2026): permutation of the items, then one permutation of each item's 16 cells; all calls
of an item are adjacent (plan 8.5). Call IDs "a13:LADDER:<item>:<variant>:<version>:<draw>".
Stop rules: response_model change (shared runner, fixed check of 297c244); the A10 stop guard
(src.replay.a10.guarded_verdict: any 429 containing "spending cap", more than 10 quota 429s within 5 minutes) with
its own guard directory logs/a13_guard/<mode>/ (a STOP file there makes the launcher refuse to start).

  .venv/bin/python -m scripts.a13.launch_ladder [--first] --plan
  .venv/bin/python -m scripts.a13.launch_ladder [--first] --workers 4          # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a13.launch_ladder [--first] --live --approved-stage a13 \
      --workers 4 > logs/a13_ladder.log 2>&1 &
--first: the first 3 items of the order, complete (6 calls per cell), read by hand before scaling (plan 23.3).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from src.replay import a10
from src.replay.r5 import build_r5
from src.replay.r5_a13 import lookup, omission_items
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.jobs import MODEL
from src.runner.runner import Job

STAGE = "a13"
CHECK = "LADDER"
SEED = 2026
FIRST_ITEMS = 3
VARIANTS = ("R2", "R3", "R4n", "R5")
VERSIONS = ("omission", "correct")
DRAWS = (1, 2)
CELLS = [(v, ver, d) for v in VARIANTS for ver in VERSIONS for d in DRAWS]


def build_messages(o: dict, variant: str, version: str) -> list:
    trace, ep = o["trace"], int(o["ep_index"])
    content = o["bob_r1_content"] if version == "omission" else None
    if variant == "R5":
        n = lookup().get((o["item_id"], version))
        if n is None:   # fail closed at run time: no matched filler, no call
            raise KeyError(f"no matched R5 filler for {o['item_id']} {version}")
        return build_r5(load_item(trace, ep), n, bob_r1_content=content)
    return build(load_item(trace, ep), variant, bob_r1_content=content)


def _job(o: dict, variant: str, version: str, draw: int) -> Job:
    item = o["item_id"]
    return Job(check=CHECK, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: build_messages(o, variant, version),
               est_input_tokens=input_tokens(item, variant), model=MODEL, verdict_fn=a10.verdict_fn())


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


def missing_fillers() -> list[tuple[str, str]]:
    have = lookup()
    return sorted((o["item_id"], v) for o in omission_items() for v in VERSIONS if (o["item_id"], v) not in have)


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A13 launcher (omission-version ladder R2, R3, R4n, R5)")
    ap.add_argument("--first", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    name = "first_jobs" if a.first else "jobs"
    js = globals()[name]()
    for v in VARIANTS:
        report_plan(f"A13 {v}{' stage 1' if a.first else ''}", [j for j in js if j.variant == v])
    report_plan(f"A13 total{' stage 1' if a.first else ''}", js)
    miss = missing_fillers()
    if miss:
        print(f"a13: {len(miss)} item-versions without a matched R5 filler: {miss}", flush=True)
    if a.plan:
        return None
    if miss:   # fail closed before any call
        sys.exit("a13: refused: R5 fillers missing (run src.replay.r5_a13 first)")
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a13_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a13: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # the A10 guard's directory variable; inherited by the workers
    rdir, qdir = DIRS[mode]
    stats = run_parallel(f"scripts.a13.launch_ladder:{name}", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a13: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
