"""A07 launcher: R6s source enumeration (D28, A07 "D27") and R6 on the omission versions (stage "a07", cap 6 USD).

Job list (`jobs`), Gemini 3.1 Flash-Lite, Shi et al.'s parameters (as the main run), on the 50 validated
D25 omission items (data/derived/omission_baits/):
  check "R6S":  R6s x2 on the omission version, R6s x2 on the correct version
                (cut context + one prompt sentence + `source_items` field + gate; src.replay.r6s);
  check "R6OM": R6 x2 on the omission version (the existing answer-side itemization, D13; src.replay.r6),
                descriptive only.
  The comparison cells R1 (omission) and R0' (correct) exist already (a06 and main run); none is rerun.
  Order: numpy default_rng(2026): permutation of the items, then one permutation of each item's 6 cells.
  All calls of an item are adjacent (plan 8.5).
Call IDs "a07:<check>:<item>:<variant>:<version>:<draw>"; versions "omission" / "correct".

Two launch stages (plan 23.3, "read the first 5 calls per cell before scaling"):
  --first   the first 3 items of the order, complete (6 calls per cell), read by hand before scaling;
  (default) the full list; calls already logged are skipped by call ID (one dataset).

  .venv/bin/python -m scripts.a07.launch_r6s [--first] --plan
  .venv/bin/python -m scripts.a07.launch_r6s [--first] --workers 4                   # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a07.launch_r6s [--first] --live --approved-stage a07 \
      --workers 4 > logs/a07_r6s_<stage>.log 2>&1 &
"""
from __future__ import annotations

import argparse
import functools

import numpy as np

from scripts.a06.launch_addendum import omission_items
from src.replay import r6, r6s
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.jobs import MODEL, original_bob_message
from src.runner.runner import Job

STAGE = "a07"
SEED = 2026
FIRST_ITEMS = 3
CELLS = [("R6S", "R6s", "omission", 1), ("R6S", "R6s", "omission", 2), ("R6S", "R6s", "correct", 1),
         ("R6S", "R6s", "correct", 2), ("R6OM", "R6", "omission", 1), ("R6OM", "R6", "omission", 2)]


def _job(o: dict, check: str, variant: str, version: str, draw: int) -> Job:
    item, trace, ep = o["item_id"], o["trace"], int(o["ep_index"])
    if version == "omission":
        content, raw = o["bob_r1_content"], o["omission_raw_log"]
    else:
        content, raw = original_bob_message(trace, ep)
    mod = r6s if variant == "R6s" else r6
    run = r6s.run_r6s if variant == "R6s" else r6.run_r6
    bob = content if version == "omission" else None   # None: the original round-1 message (R0')

    def builder():
        return mod.with_prompt_sentence(build(load_item(trace, ep), "CUT", bob_r1_content=bob))
    return Job(check=check, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=builder,
               est_input_tokens=2 * input_tokens(item, "CUT"),   # pre-check covers the gate retry
               model=MODEL, verdict_fn=functools.partial(run, bob_r1_content=content, raw_log=raw))


def jobs() -> list[Job]:
    rng = np.random.default_rng(SEED)
    om = omission_items()
    out = []
    for i in rng.permutation(len(om)):
        cells = [_job(om[i], *c) for c in CELLS]
        out += [cells[k] for k in rng.permutation(len(cells))]
    return out


def first_jobs() -> list[Job]:
    js = jobs()
    keep = list(dict.fromkeys(j.item_id for j in js))[:FIRST_ITEMS]
    return [j for j in js if j.item_id in keep]


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A07 launcher (R6s, R6 on omission versions)")
    ap.add_argument("--first", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    js = first_jobs() if a.first else jobs()
    for chk in ("R6S", "R6OM"):
        report_plan(f"A07 {chk}{' stage 1' if a.first else ''}", [j for j in js if j.check == chk])
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    rdir, qdir = DIRS[mode]
    factory = "scripts.a07.launch_r6s:" + ("first_jobs" if a.first else "jobs")
    stats = run_parallel(factory, max(1, a.workers), stage=STAGE, mode=mode, results_dir=rdir, requests_dir=qdir,
                         approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a07: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
