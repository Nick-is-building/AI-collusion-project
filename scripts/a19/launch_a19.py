"""A19 launcher (D44): broader positive control, instructed collusion on commissions and a softer agreement;
stage "a19", cap 10 USD; Gemini 3.1 Flash-Lite, Shi et al.'s parameters as in the main run.

Units (item blocks) and cells, 2 draws each (1,072 calls):
  COM unit, one per preregistered main-run item (109; check "COM", 8 calls):
    AGREE bait (main-run R1 context: cut, main-run commission bait + AGREE block), AGREE correct (R0' context + AGREE),
    SOFT bait, SOFT correct.
  OM unit, one per D25 omission item (50; check "OM", 4 calls):
    SOFT omission (R1-om context + SOFT block), SOFT correct (R0' context + SOFT).
  Call IDs "a19:<COM|OM>:<item>:<variant>:<version>:<draw>". The 22 items in both lists have one COM and one OM unit;
  their R0' + SOFT contexts are identical in both units and are run in each (cells as listed in the assignment).
Baselines reused, not rerun: main-run R1 bait and R0' (commissions), a06 R1-om and R0' (omissions), A18 AGREE.
Order: one numpy default_rng(2026): a permutation of the 159 units (109 COM in main-list order, then 50 OM in sorted
order), then a permutation of each unit's cells; all calls of a unit adjacent. Parts: "first" = the first 3 COM and
the first 2 OM units of that order (stage 1, 32 calls, read by hand); "all" = all 1,072 (the runner skips call IDs
already complete, so stage 1 is not rerun).
Every call goes through the A10 stop guard (src.replay.a14.plain_verdict_fn); guard files in logs/a19_guard/<mode>/
(a STOP file there makes the launcher refuse to start). response_model: the runner's stop rule (as A10/A14/A18).

  .venv/bin/python -m scripts.a19.launch_a19 --part all --plan
  PYTHONPATH=. .venv/bin/python -m scripts.a19.launch_a19 --part all --workers 4                    # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a19.launch_a19 --part first --live --approved-stage a19 --workers 4 \
      > logs/a19_first.log 2>&1 &
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from scripts.a06.launch_addendum import omission_items
from src.replay import a10, a14, a19
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.item_lists import load_bait, main_items
from src.runner.jobs import MODEL
from src.runner.runner import Job

STAGE = "a19"
SEED = 2026
FIRST_COM, FIRST_OM = 3, 2
COM_CELLS = [(v, ver, d) for v in ("AGREE", "SOFT") for ver in ("bait", "correct") for d in (1, 2)]
OM_CELLS = [("SOFT", ver, d) for ver in ("omission", "correct") for d in (1, 2)]
PARTS = ("first", "all")


def bob_content(kind: str, item_id: str, o: dict | None, version: str):
    if version == "correct":
        return None                                    # Bob's original round-1 message (R0')
    if kind == "COM" and version == "bait":
        return load_bait(item_id)["bob_r1_content"]    # main-run commission bait (R1)
    if kind == "OM" and version == "omission":
        return o["bob_r1_content"]                     # D25 omission version (R1-om)
    raise ValueError((kind, version))


def base_messages(kind: str, item_id: str, trace: str, ep: int, o: dict | None, version: str) -> list:
    return build(load_item(trace, ep), "CUT", bob_r1_content=bob_content(kind, item_id, o, version))


def units() -> list[dict]:
    m = main_items()
    com = [dict(kind="COM", item_id=r.item_id, trace=r.trace, ep=int(r.ep_index), task_type=r.task_type, o=None)
           for r in m.itertuples()]
    om = [dict(kind="OM", item_id=o["item_id"], trace=o["trace"], ep=int(o["ep_index"]), task_type=o["task_type"],
               o=o) for o in omission_items()]
    return com + om


def messages(u: dict, variant: str, version: str) -> list:
    return a19.with_note_block(base_messages(u["kind"], u["item_id"], u["trace"], u["ep"], u["o"], version), variant)


def _job(u: dict, variant: str, version: str, draw: int) -> Job:
    return Job(check=u["kind"], item_id=u["item_id"], variant=variant, version=version, draw=draw, judge="alice",
               task_type=u["task_type"], build_messages=lambda: messages(u, variant, version),
               est_input_tokens=input_tokens(u["item_id"], "CUT"), model=MODEL, verdict_fn=a14.plain_verdict_fn())


def jobs() -> list[Job]:
    rng = np.random.default_rng(SEED)
    us = units()
    out = []
    for i in rng.permutation(len(us)):
        u = us[i]
        b = [_job(u, *c) for c in (COM_CELLS if u["kind"] == "COM" else OM_CELLS)]
        out += [b[k] for k in rng.permutation(len(b))]
    return out


def first_units(js: list[Job]) -> list[tuple[str, str]]:
    order = list(dict.fromkeys((j.check, j.item_id) for j in js))
    return [u for u in order if u[0] == "COM"][:FIRST_COM] + [u for u in order if u[0] == "OM"][:FIRST_OM]


def part_jobs(part: str) -> list[Job]:
    js = jobs()
    if part == "all":
        return js
    if part == "first":
        keep = set(first_units(js))
        return [j for j in js if (j.check, j.item_id) in keep]
    raise ValueError(part)


def first_jobs():
    return part_jobs("first")


def all_jobs():
    return part_jobs("all")


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A19 launcher (AGREE, SOFT on commissions; SOFT on omissions)")
    ap.add_argument("--part", choices=PARTS, required=True)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    js = part_jobs(a.part)
    for k, v, ver in (("COM", "AGREE", "bait"), ("COM", "AGREE", "correct"), ("COM", "SOFT", "bait"),
                      ("COM", "SOFT", "correct"), ("OM", "SOFT", "omission"), ("OM", "SOFT", "correct")):
        report_plan(f"A19 {a.part} {k} {v}|{ver}", [j for j in js if (j.check, j.variant, j.version) == (k, v, ver)])
    report_plan(f"A19 {a.part} total", js)
    if a.plan:
        return None
    mode = "live" if a.live else "mock"
    gdir = a10.ROOT / "logs" / "a19_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a19: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)   # the A10 guard's directory variable, inherited by the workers
    rdir, qdir = DIRS[mode]
    stats = run_parallel(f"scripts.a19.launch_a19:{a.part}_jobs", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a19: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
