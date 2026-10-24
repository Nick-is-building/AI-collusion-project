"""A06 addendum launcher: D25 omission baits and D26 R5-post (stage "a06", cap 10 USD for both).

Job list (`jobs`), all Gemini 3.1 Flash-Lite, Shi et al.'s parameters (as the main run):
  D25 (check "OMIT"), per validated omission item (data/derived/omission_baits/, 50 items):
    omission version: R1 x2 (cut context), R4 x2;
    correct counterparts R0' x2 and R4-correct x2, only for items NOT in the main list (D25: "reused from
    the main run where they exist and run where missing"; main-list items have them in the main run).
  D26 (check "R5POST"), per R1-live item (40): R5post x2 on the bait version
    (src.replay.r5post; filler table data/derived/r5post_fillers.csv; fails closed if an item has no
    matched filler).
  Order: numpy default_rng(2026): permutation of the D25 items, one permutation of each item's cells, then
  the same for the D26 items. All calls of an item are adjacent (plan 8.5).
Version label "omission" for D25 omission calls; call IDs "a06:<check>:<item>:<variant>:<version>:<draw>".

  .venv/bin/python -m scripts.a06.launch_addendum --plan
  .venv/bin/python -m scripts.a06.launch_addendum --workers 4                      # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a06.launch_addendum --live --approved-stage a06 --workers 4 \
      > logs/a06_addendum.log 2>&1 &
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.replay.r5post import OUT as R5POST_TABLE, build_r5post
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.item_lists import load_bait_content, main_items, r1live_subset
from src.runner.jobs import MODEL
from src.runner.runner import Job

ROOT = Path(__file__).resolve().parents[2]
OMISSION_DIR = ROOT / "data" / "derived" / "omission_baits"
STAGE = "a06"
SEED = 2026


def omission_items() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(OMISSION_DIR.glob("rep*_alice.json"))]


def _job(check, item, trace, ep, task_type, variant, version, draw, builder, est):
    return Job(check=check, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type=task_type, build_messages=builder, est_input_tokens=est, model=MODEL)


def omission_cells(o: dict, in_main: bool) -> list:
    item, trace, ep = o["item_id"], o["trace"], int(o["ep_index"])
    content = o["bob_r1_content"]
    cells = []
    for variant, bv in (("R1", "CUT"), ("R4", "R4")):
        for d in (1, 2):
            cells.append(("omission", variant, bv, d, content))
    if not in_main:
        for variant, bv in (("R0p", "CUT"), ("R4", "R4")):
            for d in (1, 2):
                cells.append(("correct", variant, bv, d, None))
    out = []
    for version, variant, bv, d, c in cells:
        def builder(bv=bv, c=c):
            return build(load_item(trace, ep), bv, bob_r1_content=c)
        out.append(_job("OMIT", item, trace, ep, "record_extraction", variant, version, d, builder,
                        input_tokens(item, bv)))
    return out


def r5post_table() -> dict:
    if not R5POST_TABLE.exists():
        return {}
    d = pd.read_csv(R5POST_TABLE)
    return {r.item_id: int(r.n_chars) for r in d.itertuples() if bool(r.within_tolerance)}


def r5post_cells(row) -> list:
    item, trace, ep = row.item_id, row.trace, int(row.ep_index)
    out = []
    for d in (1, 2):
        def builder():
            n = r5post_table().get(item)
            if n is None:   # fail closed at run time
                raise KeyError(f"no matched R5-post filler for {item}")
            return build_r5post(load_item(trace, ep), n, load_bait_content(item))
        out.append(_job("R5POST", item, trace, ep, row.task_type, "R5post", "bait", d, builder,
                        input_tokens(item, "R0")))
    return out


def jobs() -> list[Job]:
    rng = np.random.default_rng(SEED)
    main_ids = set(main_items().item_id)
    js = []
    om = omission_items()
    for i in rng.permutation(len(om)):
        cells = omission_cells(om[i], om[i]["item_id"] in main_ids)
        js += [cells[k] for k in rng.permutation(len(cells))]
    m = main_items().set_index("item_id").loc[r1live_subset()].reset_index()
    for i in rng.permutation(len(m)):
        cells = r5post_cells(m.iloc[i])
        js += [cells[k] for k in rng.permutation(len(cells))]
    return js


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A06 addendum launcher (D25, D26)")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    js = jobs()
    for chk in ("OMIT", "R5POST"):
        report_plan(f"A06 {chk}", [j for j in js if j.check == chk])
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    rdir, qdir = DIRS[mode]
    stats = run_parallel("scripts.a06.launch_addendum:jobs", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a06: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
