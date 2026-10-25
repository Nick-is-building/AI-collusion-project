"""A16 launcher (D39): Gemini 3.8 Flash judging in Gemini 3.1 Flash-Lite's trajectories, on the identical D25 contexts
(stage "a16", cap 40 USD, check "XVER", model gemini/gemini-3.8-flash called explicitly).

Cells per D25 item (src.replay.a16; contexts byte-identical to the Flash-Lite calls of a06/main/A13/A14):
  omission, draws 1-2: R1, R4, R2, R1+CHK;   correct, draws 1-2: R0p, R4, R2, R1+CHK;
  commission (version "bait"), draw 1: R1 = R1-com, only the 22 D25 items in the main list.
  16 calls per item (+1 for shared items): 822 calls.
Order: numpy default_rng(2026): permutation of the 50 items, then one permutation of each item's cells; item blocks
adjacent (plan 8.5). Call IDs "a16:XVER:<item>:<variant>:<version>:<draw>".
Parts (--part):
  stage0a  1 call: R4 correct, draw 1, on the first item of the order (availability, price, response_models)
  stage0b  9 calls: R1, R2, R1+CHK omission, draw 1, on the first 3 items (history / thought-signature acceptance)
  first    stage 1: the first 3 items, all cells (includes the stage-0 calls, which the runner skips as done)
  all      the full list
--drop a[,b[,c]] (A16 drop order, only after a recorded D39 drop note): a = R1-com; b = draw 2 of R1+CHK (both
versions); c = draw 2 of every remaining cell.
Stop rules: the runner's response_model rule; the A16 guard (src.replay.a16: A10 429 rules, any HTTP 400, any served
model other than gemini-3.8-flash) with guard directory logs/a16_guard/<mode>/; a STOP file there makes the launcher
refuse to start.

  .venv/bin/python -m scripts.a16.launch_a16 --part all --plan
  .venv/bin/python -m scripts.a16.launch_a16 --part all --workers 4          # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a16.launch_a16 --part stage0a --live --approved-stage a16 \
      --workers 1 > logs/a16_stage0a.log 2>&1 &
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from src.replay import a10, a16
from src.runner.runner import Job, normalize_model

STAGE = "a16"
CHECK = "XVER"
SEED = 2026
MODEL = a16.MODEL_38_FLASH
FIRST_ITEMS = 3
PARTS = ("stage0a", "stage0b", "first", "all")
DROP_ENV = "A16_DROP"   # inherited by the spawned workers (they rebuild the job list from the factory)


def jobs(drop: str | None = None) -> list[Job]:
    drop = set((drop if drop is not None else os.environ.get(DROP_ENV, "")).replace(",", " ").split())
    if not drop <= {"a", "b", "c"}:
        raise ValueError(f"unknown drop {drop}")
    rng = np.random.default_rng(SEED)
    om = a16.omission_items()
    shared = a16.shared_items()
    out = []
    for i in rng.permutation(len(om)):
        js = [a16.make_job(om[i], v, ver, d, model=MODEL, check=CHECK)
              for v, ver, d in a16.item_cells(om[i]["item_id"], shared)]
        out += [js[k] for k in rng.permutation(len(js))]
    if "a" in drop:
        out = [j for j in out if (j.variant, j.version) != a16.COM_CELL]
    if "b" in drop:
        out = [j for j in out if not (j.variant == "R1+CHK" and j.draw == 2)]
    if "c" in drop:
        out = [j for j in out if j.draw == 1]
    return out


def first_items(js: list[Job]) -> list[str]:
    return list(dict.fromkeys(j.item_id for j in js))[:FIRST_ITEMS]


def part_jobs(part: str) -> list[Job]:
    js = jobs()
    if part == "all":
        return js
    keep = first_items(js)
    if part == "first":
        return [j for j in js if j.item_id in keep]
    if part == "stage0a":
        return [j for j in js if j.item_id == keep[0] and (j.variant, j.version, j.draw) == ("R4", "correct", 1)]
    if part == "stage0b":
        return [j for j in js if j.item_id in keep and j.version == "omission" and j.draw == 1
                and j.variant in ("R1", "R2", "R1+CHK")]
    raise ValueError(part)


def stage0a_jobs():
    return part_jobs("stage0a")


def stage0b_jobs():
    return part_jobs("stage0b")


def first_jobs():
    return part_jobs("first")


def all_jobs():
    return part_jobs("all")


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A16 launcher (Gemini 3.8 Flash on the D25 contexts)")
    ap.add_argument("--part", choices=PARTS, required=True)
    ap.add_argument("--drop", default="", help="a16 drop order letters, e.g. 'a' or 'a,b'")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    os.environ[DROP_ENV] = a.drop
    js = part_jobs(a.part)
    cells = sorted({(j.variant, j.version) for j in js})
    for v, ver in cells:
        report_plan(f"A16 {a.part} {v}|{ver}", [j for j in js if (j.variant, j.version) == (v, ver)])
    report_plan(f"A16 {a.part} total (drop {a.drop or '-'})", js)
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a16_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a16: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # the guard's directory variable; inherited by the workers
    # expected served model for the A16 guard: the requested model in live mode; the mock backend's name in mock mode
    os.environ[a16.EXPECT_ENV] = normalize_model(MODEL) if mode == "live" else "mock-model"
    rdir, qdir = DIRS[mode]
    stats = run_parallel(f"scripts.a16.launch_a16:{a.part}_jobs", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a16: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
