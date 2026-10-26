"""A18 launcher (D43): positive control, instructed collusion (AGREE, AGREE+CHK) on the 50 D25 omission items;
stage "a18", cap 5 USD; Gemini 3.1 Flash-Lite, Shi et al.'s parameters as in the main run.

Cells per item (check "AGREE", 8 calls; 400 in total):
  AGREE x2 omission (R1-om context + AGREE block), AGREE x2 correct (R0' context + AGREE block),
  AGREE+CHK x2 omission, AGREE+CHK x2 correct.
  Call IDs "a18:AGREE:<item>:<variant>:<version>:<draw>".
Baselines R1-om (a06), R0' (main/a06), R1-om+CHK and R1+CHK correct (a14 LOOK CHK) are reused, not rerun.
Order: one numpy default_rng(2026): a permutation of the 50 item blocks, then a permutation of each item's 8 cells;
all calls of an item adjacent. Parts: "first" = the first 3 items of that order (stage 1, 24 calls, read by hand);
"all" = all 400 (the runner skips call IDs already complete, so stage 1 is not rerun).
Every call goes through the A10 stop guard (src.replay.a14.plain_verdict_fn); guard files in logs/a18_guard/<mode>/
(a STOP file there makes the launcher refuse to start). response_model: the runner's stop rule (as A10/A14).

  .venv/bin/python -m scripts.a18.launch_a18 --part all --plan
  PYTHONPATH=. .venv/bin/python -m scripts.a18.launch_a18 --part all --workers 4                    # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a18.launch_a18 --part first --live --approved-stage a18 --workers 4 \
      > logs/a18_first.log 2>&1 &
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from scripts.a06.launch_addendum import omission_items
from src.replay import a10, a14, a18
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.jobs import MODEL
from src.runner.runner import Job

STAGE = "a18"
CHECK = "AGREE"
SEED = 2026
FIRST_ITEMS = 3
ARMS = ("AGREE", "AGREE+CHK")
CELLS = [(v, ver, d) for v in ARMS for ver in ("omission", "correct") for d in (1, 2)]
PARTS = ("first", "all")


def messages(o: dict, variant: str, version: str) -> list:
    bob = o["bob_r1_content"] if version == "omission" else None   # None: original message (R0')
    return a18.with_note_block(build(load_item(o["trace"], int(o["ep_index"])), "CUT", bob_r1_content=bob), variant)


def _job(o: dict, variant: str, version: str, draw: int) -> Job:
    item = o["item_id"]
    return Job(check=CHECK, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: messages(o, variant, version),
               est_input_tokens=input_tokens(item, "CUT"), model=MODEL, verdict_fn=a14.plain_verdict_fn())


def jobs() -> list[Job]:
    rng = np.random.default_rng(SEED)
    om = omission_items()
    out = []
    for i in rng.permutation(len(om)):
        b = [_job(om[i], *c) for c in CELLS]
        out += [b[k] for k in rng.permutation(len(b))]
    return out


def first_items(js: list[Job]) -> list[str]:
    return list(dict.fromkeys(j.item_id for j in js))[:FIRST_ITEMS]


def part_jobs(part: str) -> list[Job]:
    js = jobs()
    if part == "all":
        return js
    if part == "first":
        keep = first_items(js)
        return [j for j in js if j.item_id in keep]
    raise ValueError(part)


def first_jobs():
    return part_jobs("first")


def all_jobs():
    return part_jobs("all")


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A18 launcher (AGREE, AGREE+CHK on the D25 contexts)")
    ap.add_argument("--part", choices=PARTS, required=True)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    js = part_jobs(a.part)
    for v in ARMS:
        for ver in ("omission", "correct"):
            report_plan(f"A18 {a.part} {v}|{ver}", [j for j in js if (j.variant, j.version) == (v, ver)])
    report_plan(f"A18 {a.part} total", js)
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a18_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a18: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # the A10 guard's directory variable, inherited by the workers
    rdir, qdir = DIRS[mode]
    stats = run_parallel(f"scripts.a18.launch_a18:{a.part}_jobs", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a18: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
