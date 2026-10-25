"""Reading aid for A16 live calls (plan 23.3) and the stage-1 cost projection. Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a16.read_stage --part stage0a        # checks + reasoning of each call
  PYTHONPATH=. .venv/bin/python -m scripts.a16.read_stage --part first > scratch/a16/stage1_read.txt
  PYTHONPATH=. .venv/bin/python -m scripts.a16.read_stage --part all --checks-only
  PYTHONPATH=. .venv/bin/python -m scripts.a16.read_stage --project [--drop a,b,c]
Checks per call (`check_call`):
  - the saved request's messages == the cell's built messages (canonical JSON), and their SHA-256 == the logged
    messages_sha256 of every Flash-Lite call of the same item, cell and version (src.replay.a16.flash_lite_call_ids);
  - the saved request == the saved Flash-Lite request of the same cell except `model` and `allowed_openai_params`
    (when that Flash-Lite payload exists locally; results/requests/ is not committed);
  - model gemini/gemini-3.8-flash, temperature 1.0, max_tokens 64,000, reasoning_effort high, forced submit_verdict;
  - response_models (every usage record, provider prefix stripped) == {gemini-3.8-flash}.
--project: mean logged cost per call of each cell (live a16 lines) x the number of calls of that cell in the full list
(after --drop); cells without a logged call are projected from the runner's no-cache estimate and flagged.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from scripts.a16 import launch_a16 as L
from src.replay import a16
from src.replay.request import canonical_json, messages_hash
from src.runner.costs import PriceTable, iter_call_lines
from src.runner.estimates import projected_call_cost
from src.runner.runner import normalize_model

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
REQ = ROOT / "results" / "requests"
FL_STAGES = ("main", "a06", "a13", "a14")
IGNORED_KWARGS = ("model", "allowed_openai_params")


@lru_cache(maxsize=1)
def flash_lite_lines() -> dict:
    return {r["call_id"]: r for r in iter_call_lines(RAW) if r.get("mode") == "live" and r.get("stage") in FL_STAGES}


@lru_cache(maxsize=1)
def items() -> dict:
    return {o["item_id"]: o for o in a16.omission_items()}


@lru_cache(maxsize=1)
def main_ids() -> frozenset:
    return frozenset(a16.shared_items())


def load_request(run_id: str, h: str) -> dict | None:
    p = REQ / run_id / f"{h}.json.gz"
    return json.loads(gzip.open(p, "rt").read()) if p.exists() else None


def flash_lite_sources(item: str, variant: str, version: str) -> list[dict]:
    fl = flash_lite_lines()
    ids = a16.flash_lite_call_ids(item, variant, version, item in main_ids())
    return [fl[c] for c in ids if c in fl]


def check_call(rec: dict) -> list[str]:
    probs = []
    o = items()[rec["item_id"]]
    built = a16.build_messages(o, rec["variant"], rec["version"])
    srcs = flash_lite_sources(rec["item_id"], rec["variant"], rec["version"])
    if not srcs:
        probs.append("no Flash-Lite source line")
    if any(s["messages_sha256"] != messages_hash(built) for s in srcs):
        probs.append("built messages hash != Flash-Lite messages_sha256")
    if rec.get("messages_sha256") != messages_hash(built):
        probs.append("logged messages_sha256 != built")
    for n, h in enumerate(rec["request_sha256"]):
        req = load_request(rec["run_id"], h)
        if req is None:
            probs.append(f"request payload {n} not found locally")
            continue
        if n == 0:
            if canonical_json(req["messages"]) != canonical_json(built):
                probs.append("saved request messages != built messages")
            fl_req = next((q for q in (load_request(s["run_id"], s["request_sha256"][0]) for s in srcs
                                       if s.get("request_sha256")) if q is not None), None)
            if fl_req is not None:
                a = {k: v for k, v in req.items() if k not in IGNORED_KWARGS}
                b = {k: v for k, v in fl_req.items() if k not in IGNORED_KWARGS}
                if canonical_json(a) != canonical_json(b):
                    probs.append("request != Flash-Lite request (beyond model / allowed_openai_params): "
                                 + ",".join(sorted(k for k in set(a) | set(b) if canonical_json(a.get(k)) != canonical_json(b.get(k)))))
        if req.get("model") != L.MODEL or req.get("temperature") != 1.0 or req.get("max_tokens") != 64000 \
                or req.get("reasoning_effort") != "high":
            probs.append("params")
        tc = req.get("tool_choice")
        if not (isinstance(tc, dict) and tc.get("function", {}).get("name") == "submit_verdict"):
            probs.append(f"tool_choice {tc}")
    served = {normalize_model(m) for m in rec.get("response_models") or []}
    if served != {"gemini-3.8-flash"}:
        probs.append(f"response_models {rec.get('response_models')}")
    return probs


def a16_lines() -> dict:
    return {r["call_id"]: r for r in iter_call_lines(RAW) if r.get("stage") == L.STAGE and r.get("mode") == "live"}


def project(drop: str) -> None:
    os.environ[L.DROP_ENV] = drop
    js = L.jobs(drop)
    recs = a16_lines()
    cost = defaultdict(list)
    for r in recs.values():
        cost[(r["variant"], r["version"])].append(r.get("cost_usd") or 0.0)
    prices, total = PriceTable(), 0.0
    by_cell = defaultdict(list)
    for j in js:
        by_cell[(j.variant, j.version)].append(j)
    for k, cj in sorted(by_cell.items()):
        if cost.get(k):
            per = sum(cost[k]) / len(cost[k])
            src = f"measured mean of {len(cost[k])} calls"
        else:
            per = sum(projected_call_cost(prices, j.model, j.est_input_tokens) for j in cj) / len(cj)
            src = "NO MEASURED CALL: runner estimate"
        total += per * len(cj)
        print(f"{k[0]}|{k[1]}: {len(cj)} calls x {per:.4f} USD = {per * len(cj):.3f} USD ({src})")
    spent = sum(r.get("cost_usd") or 0.0 for r in recs.values())
    print(f"projected full run (drop {drop or '-'}): {len(js)} calls, {total:.3f} USD; spent so far {spent:.4f} USD "
          f"on {len(recs)} calls")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=L.PARTS, default="first")
    ap.add_argument("--checks-only", action="store_true")
    ap.add_argument("--project", action="store_true")
    ap.add_argument("--drop", default="")
    a = ap.parse_args(argv)
    if a.project:
        project(a.drop)
        return
    want = [j.call_id(L.STAGE) for j in L.part_jobs(a.part)]
    recs = a16_lines()
    n_probs, n_logged = 0, 0
    for cid in want:
        r = recs.get(cid)
        if r is None:
            if not a.checks_only:
                print(f"== {cid}: NOT LOGGED")
            continue
        n_logged += 1
        probs = check_call(r)
        n_probs += len(probs)
        if a.checks_only:
            if probs:
                print(f"== {cid} problems={probs}")
            continue
        acc = [u for u in r.get("usage") or [] if not u.get("error_category")]
        tok = (acc[0].get("input_tokens"), acc[0].get("cached_input_tokens"), acc[0].get("billable_output_tokens")) if acc else None
        print(f"== {cid}  verdict={r['verdict']} status={r['verdict_status']} api_requests={r['n_api_requests']} "
              f"errors={r.get('api_error_counts')} response_models={r.get('response_models')} "
              f"tokens(in,cached,out)={tok} cost={r.get('cost_usd'):.4f} problems={probs or 0}")
        o = items()[r["item_id"]]
        print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
        print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# calls expected {len(want)}, logged {n_logged}, request problems {n_probs}")


if __name__ == "__main__":
    main()
