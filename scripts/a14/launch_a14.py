"""A14 launcher (D37): LOOK (VIG, CHK, R4+VIG on the 50 D25 omission items) and NAT (N1f, R6x on the 26
natural-error extraction items); stage "a14", cap 8 USD.

Cells (Gemini 3.1 Flash-Lite, Shi et al.'s parameters as in the main run):
  check "LOOK", per D25 omission item (data/derived/omission_baits/), 10 calls:
    VIG x2 omission (R1 context + VIG block), VIG x2 correct (R0' context + VIG block),
    CHK x2 omission, CHK x2 correct (same with the CHK block),
    R4+VIG x2 omission (R4 context with the omission content + VIG block)                       -> 500 calls
    Call IDs "a14:LOOK:<item>:<variant>:<version>:<draw>" (variants VIG, CHK, R4+VIG; versions omission/correct).
  check "NAT", per natural-error extraction item (26), 6 calls, cut context with Bob's original round-1 message:
    N1f x3 (the N1 context, plain verdict), R6x x3 (D30 unchanged, gated against his original raw log) -> 156 calls
    Call IDs "a14:NAT:<item>:<cell>:<draw>" (cells N1f, R6x; the version field is logged as "natural").
  Baselines R1-om, R4-om (a06), R0' (main/a06), R6x-first (a08) and the original N1 (main run) are reused, not rerun.
Order: one numpy default_rng(2026): a permutation of the 76 item blocks (50 LOOK + 26 NAT items together, so every
  cell starts early in the run and can be read by hand before the run is half done, plan 23.3), then one
  permutation of each item's cells. All calls of an item are adjacent (plan 8.5).
Every call goes through the A10 stop guard (src.replay.a14); guard files in logs/a14_guard/<mode>/ (a STOP file
there makes the launcher refuse to start).

  .venv/bin/python -m scripts.a14.launch_a14 --plan
  .venv/bin/python -m scripts.a14.launch_a14 --workers 4                    # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a14.launch_a14 --live --approved-stage a14 --workers 4 \
      > logs/a14.log 2>&1 &
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np

from scripts.a06.launch_addendum import omission_items
from scripts.a14.nat_records import nat_items
from src.replay import a10, a14, r6x
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.jobs import MODEL, original_bob_message
from src.runner.runner import Job

STAGE = "a14"
SEED = 2026
LOOK_CELLS = ([("VIG", "omission", d) for d in (1, 2)] + [("VIG", "correct", d) for d in (1, 2)]
              + [("CHK", "omission", d) for d in (1, 2)] + [("CHK", "correct", d) for d in (1, 2)]
              + [("R4+VIG", "omission", d) for d in (1, 2)])
NAT_CELLS = [("N1f", d) for d in (1, 2, 3)] + [("R6x", d) for d in (1, 2, 3)]
LOOK_BASE = {"VIG": ("CUT", "VIG"), "CHK": ("CUT", "CHK"), "R4+VIG": ("R4", "VIG")}


@dataclass
class NatJob(Job):
    """NAT call IDs carry no version (A14: "a14:NAT:<item>:<cell>:<draw>")."""

    def call_id(self, stage: str) -> str:
        return f"{stage}:{self.check}:{self.item_id}:{self.variant}:{self.draw}"


def look_messages(o: dict, variant: str, version: str) -> list:
    base, arm = LOOK_BASE[variant]
    bob = o["bob_r1_content"] if version == "omission" else None   # None: original message (R0')
    return a14.with_note_block(build(load_item(o["trace"], int(o["ep_index"])), base, bob_r1_content=bob), arm)


def nat_messages(trace: str, ep: int, cell: str) -> list:
    msgs = build(load_item(trace, ep), "CUT")   # the N1 context: cut, Bob's original round-1 message
    return r6x.with_prompt_sentence(msgs) if cell == "R6x" else msgs


def _look_job(o: dict, variant: str, version: str, draw: int) -> Job:
    item = o["item_id"]
    return Job(check="LOOK", item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: look_messages(o, variant, version),
               est_input_tokens=input_tokens(item, LOOK_BASE[variant][0]), model=MODEL,
               verdict_fn=a14.plain_verdict_fn())


def _nat_job(row, cell: str, draw: int) -> Job:
    trace, ep, item = row.trace, int(row.ep_index), row.item_id
    if cell == "R6x":
        content, raw = original_bob_message(trace, ep)
        fn, est = a14.r6x_verdict_fn(content, raw), 2 * input_tokens(item, "CUT")   # pre-check covers the retry
    else:
        fn, est = a14.plain_verdict_fn(), input_tokens(item, "CUT")
    return NatJob(check="NAT", item_id=item, variant=cell, version="natural", draw=draw, judge="alice",
                  task_type="record_extraction", build_messages=lambda: nat_messages(trace, ep, cell),
                  est_input_tokens=est, model=MODEL, verdict_fn=fn)


def jobs() -> list[Job]:
    rng = np.random.default_rng(SEED)
    blocks = [[_look_job(o, *c) for c in LOOK_CELLS] for o in omission_items()]
    blocks += [[_nat_job(r, *c) for c in NAT_CELLS] for r in nat_items().itertuples()]
    out = []
    for i in rng.permutation(len(blocks)):
        b = blocks[i]
        out += [b[k] for k in rng.permutation(len(b))]
    return out


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A14 launcher (LOOK: VIG, CHK, R4+VIG; NAT: N1f, R6x)")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    js = jobs()
    for chk in ("LOOK", "NAT"):
        report_plan(f"A14 {chk}", [j for j in js if j.check == chk])
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a14_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a14: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # the A10 guard's directory variable, inherited by the workers
    rdir, qdir = DIRS[mode]
    stats = run_parallel("scripts.a14.launch_a14:jobs", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a14: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
