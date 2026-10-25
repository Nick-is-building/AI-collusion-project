"""A10 launcher: incentive-rule arms (D32) and peer-signal arms (D33) on the 50 D25 omission items
(stage "a10", cap 25 USD).

Cells (Gemini 3.1 Flash-Lite, Shi et al.'s parameters as in the main run; src.replay.a10):
  core (check "INC" / "SIG"):  INC-R, INC-C, INC-A, SIG-N, SIG-A, each x3 on the omission version (R1 context)
                               and x2 on the correct version (R0' context)          -> 25 calls per item, 1,250
  optional (check "OPT"; only after the core full run, A10):
                               INC-P and SIG-R x3 omission, x2 correct; INC-C+SIG-A x3 omission (descriptive)
                                                                                    -> 13 calls per item, 650
  Comparison cells R1 (omission, a06) and R0' (correct, main run / a06) are reused, not rerun.
  Order: numpy default_rng(2026): permutation of the items, then one permutation of each item's cells; all
  calls of an item are adjacent (plan 8.5). The optional list uses its own default_rng(2026) in the same way.
Call IDs "a10:<check>:<item>:<variant>:<version>:<draw>"; versions "omission" / "correct".
Every call goes through the A10 stop guard (src.replay.a10.guarded_verdict); guard files in
logs/a10_guard/<mode>/ (a STOP file there makes the launcher refuse to start).

  .venv/bin/python -m scripts.a10.launch_a10 [--optional] [--first] --plan
  .venv/bin/python -m scripts.a10.launch_a10 [--optional] [--first] --workers 3          # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a10.launch_a10 [--optional] [--first] --live \
      --approved-stage a10 --workers 3 > logs/a10_<stage>.log 2>&1 &
--first: the first 3 items of the order, complete (every cell), read by hand before scaling (plan 23.3).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from scripts.a06.launch_addendum import omission_items
from src.replay import a10
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.jobs import MODEL, original_bob_message
from src.runner.runner import Job

STAGE = "a10"
SEED = 2026
FIRST_ITEMS = 3
OM_DRAWS, COR_DRAWS = (1, 2, 3), (1, 2)


def _cells(variants, check, with_correct=True):
    out = []
    for v in variants:
        out += [(check, v, "omission", d) for d in OM_DRAWS]
        if with_correct:
            out += [(check, v, "correct", d) for d in COR_DRAWS]
    return out


CORE_CELLS = _cells(a10.INC_ARMS, "INC") + _cells(a10.SIG_ARMS, "SIG")
OPTIONAL_CELLS = (_cells(a10.OPT_INC, "OPT") + _cells(a10.OPT_SIG, "OPT")
                  + _cells((a10.COMBO,), "OPT", with_correct=False))


def build_messages(o: dict, variant: str, version: str) -> list:
    """Message list of one A10 cell (R1 context on the omission version, R0' on the correct version)."""
    trace, ep = o["trace"], int(o["ep_index"])
    reward, signal = a10.arm_parts(variant)
    bob = o["bob_r1_content"] if version == "omission" else None   # None: original message (R0')
    if signal:
        base = bob if bob is not None else original_bob_message(trace, ep)[0]
        bob = a10.with_peer_signal(base, signal)
    msgs = build(load_item(trace, ep), "CUT", bob_r1_content=bob)
    return a10.with_reward_block(msgs, reward) if reward else msgs


def _job(o: dict, check: str, variant: str, version: str, draw: int) -> Job:
    item = o["item_id"]
    return Job(check=check, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: build_messages(o, variant, version),
               est_input_tokens=input_tokens(item, "CUT"), model=MODEL, verdict_fn=a10.verdict_fn())


def _ordered(cells) -> list[Job]:
    rng = np.random.default_rng(SEED)
    om = omission_items()
    out = []
    for i in rng.permutation(len(om)):
        js = [_job(om[i], *c) for c in cells]
        out += [js[k] for k in rng.permutation(len(js))]
    return out


def _first(js: list[Job]) -> list[Job]:
    keep = list(dict.fromkeys(j.item_id for j in js))[:FIRST_ITEMS]
    return [j for j in js if j.item_id in keep]


def jobs() -> list[Job]:
    return _ordered(CORE_CELLS)


def first_jobs() -> list[Job]:
    return _first(jobs())


def optional_jobs() -> list[Job]:
    return _ordered(OPTIONAL_CELLS)


def optional_first_jobs() -> list[Job]:
    return _first(optional_jobs())


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A10 launcher (incentive-rule and peer-signal arms)")
    ap.add_argument("--optional", action="store_true")
    ap.add_argument("--first", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    name = ("optional_" if a.optional else "") + ("first_jobs" if a.first else "jobs")
    js = globals()[name]()
    for chk in sorted({j.check for j in js}):
        report_plan(f"A10 {chk}{' stage 1' if a.first else ''}", [j for j in js if j.check == chk])
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a10_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a10: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # inherited by the spawned workers
    rdir, qdir = DIRS[mode]
    stats = run_parallel(f"scripts.a10.launch_a10:{name}", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a10: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
