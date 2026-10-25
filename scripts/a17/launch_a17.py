"""A17 launcher (D41): Claude Haiku 5.5 on the D25 contexts; stage "a17", cap 15 USD, Anthropic API only.

Label: "Claude Haiku 5.5 judging in Gemini 3.1 Flash-Lite's trajectories (cross-family; Gemini thought signatures
removed)". Route and converter: src.replay.a17 (upstream request builder unchanged; the request it builds is the
Flash-Lite request; the backend converts it for Anthropic).

Cells (identical to D39/A16 without its commission cell), 50 D25 omission items, 2 draws each:
  omission: R1 (= R1-om, cut), R4, R2, R1+CHK;  correct: R0p (R0'), R4, R2, R1+CHK          -> 16 per item, 800
  contexts from src.replay.a17_cells.build_messages (the same builders and arguments as the Flash-Lite stages).
Order: numpy default_rng(2026): permutation of the 50 items, then one permutation of each item's 16 cells; item blocks
adjacent. Call IDs "a17:HAIKU:<item>:<variant>:<version>:<draw>".
Parts:
  p6     10 calls: R1 omission, check "P6", on the items at positions 4-13 of the order (not in the stage-1 block);
         P6 passes if submit_verdict is returned in >= 9 of 10 calls with thinking present (`--p6-check`).
         Call IDs "a17:P6:<item>:R1:omission:1"; not used in the analysis.
  first  stage 1: the first 3 items of the order, every cell (48 calls); every call read by hand before scaling.
  all    the full list (resume skips logged call IDs).
--drop-draw2: removes draw 2 of every cell (A17: stage-1 projection above 12 USD; recorded in D41 first).

  .venv/bin/python -m scripts.a17.launch_a17 --part all --plan
  .venv/bin/python -m scripts.a17.launch_a17 --part all --workers 4                         # mock
  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m scripts.a17.launch_a17 --part p6 --live --approved-stage a17 --workers 4 \
      > logs/a17_p6.log 2>&1 &
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from scripts.a06.launch_addendum import omission_items
from src.replay import a10, a17
from src.replay.a17_cells import BASE, COR_VARIANTS, OM_VARIANTS, build_messages
from src.runner.estimates import input_tokens
from src.runner.runner import Job

STAGE, CHECK, SEED = "a17", "HAIKU", 2026
FIRST_ITEMS = 3
P6_POSITIONS = range(3, 13)
DROP_ENV = "A17_DROP_DRAW2"


def item_cells(draws: int = 2) -> list[tuple[str, str, int]]:
    cells = [(v, "omission", d) for v in OM_VARIANTS for d in range(1, draws + 1)]
    return cells + [(v, "correct", d) for v in COR_VARIANTS for d in range(1, draws + 1)]


def make_job(o: dict, variant: str, version: str, draw: int, check: str = CHECK) -> Job:
    return Job(check=check, item_id=o["item_id"], variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: build_messages(o, variant, version),
               est_input_tokens=2 * input_tokens(o["item_id"], BASE[variant]),   # Claude tokenizer margin
               model=a17.MODEL_HAIKU, verdict_fn=a17.run)


def item_order() -> tuple[list[dict], np.random.Generator]:
    rng = np.random.default_rng(SEED)
    om = omission_items()
    return [om[i] for i in rng.permutation(len(om))], rng


def jobs(drop_draw2: bool | None = None) -> list[Job]:
    drop = os.environ.get(DROP_ENV) == "1" if drop_draw2 is None else drop_draw2
    items, rng = item_order()
    out = []
    for o in items:
        js = [make_job(o, *c) for c in item_cells()]
        out += [js[k] for k in rng.permutation(len(js))]
    return [j for j in out if not (drop and j.draw == 2)]


def first_jobs() -> list[Job]:
    keep = {o["item_id"] for o in item_order()[0][:FIRST_ITEMS]}
    return [j for j in jobs() if j.item_id in keep]


def p6_jobs() -> list[Job]:
    items = item_order()[0]
    return [make_job(items[k], "R1", "omission", 1, check="P6") for k in P6_POSITIONS]


def p6_check(raw_dir) -> dict:
    """P6: submit_verdict in >= 9 of 10 calls with thinking present (thinking block in the response message)."""
    from src.runner.costs import iter_call_lines
    recs = {r["call_id"]: r for r in iter_call_lines(raw_dir) if r.get("stage") == STAGE and r.get("check") == "P6"}
    n_tool = n_both = 0
    per = []
    for r in recs.values():
        msgs = r.get("response_messages") or []
        tool = r.get("verdict_status") == "ok" and any(
            tc.get("function", {}).get("name") == "submit_verdict" for m in msgs for tc in (m.get("tool_calls") or []))
        thinking = any(m.get("thinking_blocks") or m.get("reasoning_content") for m in msgs if m.get("role") == "assistant")
        n_tool += tool
        n_both += tool and thinking
        per.append(dict(call_id=r["call_id"], submit_verdict=tool, thinking=bool(thinking), verdict=r.get("verdict")))
    return dict(calls=len(recs), submit_verdict=n_tool, submit_verdict_with_thinking=n_both,
                passed=len(recs) == 10 and n_both >= 9, per_call=per)


PARTS = {"p6": p6_jobs, "first": first_jobs, "all": jobs}


def main(argv=None):
    from scripts.main.launch_main import DIRS
    from scripts.pilot.common import report_plan
    from src.runner.parallel import run_parallel
    ap = argparse.ArgumentParser(description="A17 launcher (Claude Haiku 5.5 on the D25 contexts)")
    ap.add_argument("--part", choices=sorted(PARTS), required=True)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--drop-draw2", action="store_true")
    ap.add_argument("--p6-check", action="store_true")
    a = ap.parse_args(argv)
    mode = "live" if a.live else "mock"
    if a.p6_check:
        print(json.dumps(p6_check(DIRS[mode][0]), indent=1))
        return None
    if a.drop_draw2:
        os.environ[DROP_ENV] = "1"   # inherited by the workers
    js = PARTS[a.part]()
    report_plan(f"A17 {a.part}", js)
    if a.plan:
        return None
    gdir = a10.ROOT / "logs" / "a17_guard" / mode
    if a10.stop_file(gdir).exists():
        sys.exit(f"a17: refused: STOP file present ({a10.stop_file(gdir)}); inspect it before any relaunch")
    os.environ["A10_GUARD_DIR"] = str(gdir)
    rdir, qdir = DIRS[mode]
    factory = {"p6": "p6_jobs", "first": "first_jobs", "all": "jobs"}[a.part]
    stats = run_parallel(f"scripts.a17.launch_a17:{factory}", max(1, a.workers), stage=STAGE, mode=mode,
                         results_dir=rdir, requests_dir=qdir, approved_stage=a.approved_stage, seed=SEED)
    for s in stats:
        print(f"a17: {mode} {s}", flush=True)
    return stats


if __name__ == "__main__":
    main()
