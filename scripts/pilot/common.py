"""Shared CLI and job builders for the pilot checks (PROJECT_PLAN.md section 10).

Modes:
  default (mock)  Shi et al.'s verdict path with the mock model from src/replay/request.py; no
                  network. Output under logs/mock_runs/ (git-ignored). Mock usage reports the
                  estimated input tokens, so mock "costs" are estimates, never real spend.
  --plan          only print the calls and projected cost; nothing is executed.
  --live --approved-stage pilot
                  real API calls. Refused under pytest, without the matching approval flag, or
                  with an uncommitted working tree. NOT authorized by assignment A01.

Item tables are read at run time (data/derived/items/); nothing assumes 168 or 173 candidates.
Random choices use numpy.random.default_rng(2026), consumed in the order documented per script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.replay.request import mock_backend
from src.replay.variants import build, load_item
from src.runner.costs import PriceTable, load_yaml
from src.runner.estimates import input_tokens, projected_call_cost
from src.runner.runner import Job, Runner

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "derived" / "items"
BAITS = ROOT / "data" / "derived" / "baits"
SEED = 2026
STAGE = "pilot"
MODEL = load_yaml("models.yaml")["primary"]["route"]

DIRS = {
    "mock": (ROOT / "logs" / "mock_runs" / "raw", ROOT / "logs" / "mock_runs" / "requests"),
    "live": (ROOT / "results" / "raw", ROOT / "results" / "requests"),
}


def candidates() -> pd.DataFrame:
    return pd.read_csv(ITEMS / "candidates.csv")


def holdout() -> pd.DataFrame:
    c = candidates()
    return c[c.set == "pilot_holdout"].sort_values("item_id").reset_index(drop=True)


def fidelity() -> pd.DataFrame:
    return pd.read_csv(ITEMS / "fidelity_set.csv")


def parse_ep(item_id: str) -> int:
    return int(item_id.split("_e")[1][:2]) - 1


def make_job(check, row, variant, version="correct", draw=1, bob_r1_content=None, model=MODEL,
             judge="alice", allow_undocumented_price=False) -> Job:
    trace, ep = row.trace, int(row.ep_index)
    build_variant = {"R0p": "CUT", "R1": "CUT"}.get(variant, variant)

    def builder():
        return build(load_item(trace, ep, judge), build_variant, bob_r1_content=bob_r1_content)

    return Job(check=check, item_id=row.item_id, variant=variant, version=version, draw=draw, judge=judge,
               task_type=row.task_type, build_messages=builder,
               est_input_tokens=input_tokens(row.item_id, "R0" if variant == "R0" else build_variant),
               model=model, allow_undocumented_price=allow_undocumented_price)


def load_bait(item_id: str) -> str | None:
    p = BAITS / f"{item_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("bob_r1_content")


def rng():
    return np.random.default_rng(SEED)


def parser(desc: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--plan", action="store_true", help="print calls and projected cost only")
    ap.add_argument("--live", action="store_true", help="real API calls (needs --approved-stage pilot)")
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--results-dir", type=Path, default=None)
    ap.add_argument("--requests-dir", type=Path, default=None)
    return ap


def report_plan(name: str, jobs: list[Job], prices: PriceTable | None = None) -> float:
    prices = prices or PriceTable()
    total = 0.0
    for j in jobs:
        if prices.documented(j.model) or j.allow_undocumented_price:
            total += projected_call_cost(prices, j.model, j.est_input_tokens)
    est_in = sum(j.est_input_tokens for j in jobs)
    undocumented = sorted({j.model for j in jobs if not prices.documented(j.model)})
    print(f"{name}: {len(jobs)} calls (one verdict job each; up to 3 attempts), est. input tokens {est_in:,}, "
          f"projected cost {total:.3f} USD" + (f"  [undocumented price, placeholder used: {undocumented}]"
                                                if undocumented else ""))
    return total


def execute(name: str, jobs: list[Job], args, *, mock_verdict="accept", extra_note=None) -> dict | None:
    projected = report_plan(name, jobs)
    if extra_note:
        print(extra_note)
    if args.plan or not jobs:
        return None
    mode = "live" if args.live else "mock"
    rdir, qdir = DIRS[mode]
    rdir = args.results_dir or rdir
    qdir = args.requests_dir or qdir
    backend = None
    if mode == "mock":
        # mock usage reports input tokens = request characters / 4 (a stand-in, not a count), so the
        # cost path is exercised end to end
        def backend(**kw):
            n = len(json.dumps(kw["messages"], default=str)) // 4
            return mock_backend(mock_verdict, input_tokens=n)(**kw)
    runner = Runner(stage=STAGE, mode=mode, results_dir=rdir, requests_dir=qdir, backend=backend,
                    approved_stage=args.approved_stage, seed=SEED)
    stats = runner.run(jobs)
    print(f"{name}: {mode} run {runner.run_id}: {stats} -> {runner.path}")
    stats["run_path"] = str(runner.path)
    stats["projected"] = projected
    return stats


def read_calls(path) -> list[dict]:
    out = []
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        if r.get("type") == "call":
            out.append(r)
    return out


def execute_parallel(name: str, factory: str, jobs: list[Job], args) -> list[dict] | None:
    """Like `execute`, but runs `factory` in args.workers processes (src.runner.parallel)."""
    from src.runner.parallel import run_parallel
    report_plan(name, jobs)
    if args.plan or not jobs:
        return None
    mode = "live" if args.live else "mock"
    rdir, qdir = DIRS[mode]
    stats = run_parallel(factory, max(1, args.workers), stage=STAGE, mode=mode, results_dir=args.results_dir or rdir,
                         requests_dir=args.requests_dir or qdir, approved_stage=args.approved_stage, seed=SEED)
    for s in stats:
        print(f"{name}: {mode} {s}")
    return stats
