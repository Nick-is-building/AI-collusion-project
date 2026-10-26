"""Reading aid for A19 live calls (plan 23.3; A19 stage 1: every call read by hand). Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a19.read_stage --part first > scratch/a19/stage1_read.txt
  PYTHONPATH=. .venv/bin/python -m scripts.a19.read_stage --part all --checks-only
Checks per call: the first saved request's messages equal the job's built messages (canonical JSON); relative to
the base context (main-run R1 bait / R1-om / R0', cut) only the final verdict prompt differs, by exactly "\n\n" + the
arm's block; model gemini/gemini-3.1-flash-lite, temperature 1.0, max_tokens 64,000, reasoning_effort high, forced
submit_verdict; response_models == [gemini-3.1-flash-lite].
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from scripts.a19 import launch_a19 as L
from src.replay import a19
from src.replay.request import canonical_json
from src.runner.costs import iter_call_lines
from src.runner.item_lists import load_bait

ROOT = Path(__file__).resolve().parents[2]
DIRS = {"live": (ROOT / "results" / "raw", ROOT / "results" / "requests"),
        "mock": (ROOT / "logs" / "mock_runs" / "raw", ROOT / "logs" / "mock_runs" / "requests")}


def _same(a, b):
    return canonical_json(a) == canonical_json(b)


def check_call(rec: dict, units: dict, qdir: Path, mode: str) -> list[str]:
    probs = []
    u = units[(rec["check"], rec["item_id"])]
    base = L.base_messages(u["kind"], u["item_id"], u["trace"], u["ep"], u["o"], rec["version"])
    built = L.messages(u, rec["variant"], rec["version"])
    diff = [i for i in range(len(base)) if not _same(built[i], base[i])]
    if len(built) != len(base) or diff != [len(base) - 1]:
        probs.append(f"diff positions {diff}")
    if built[-1]["content"] != base[-1]["content"] + "\n\n" + a19.note_block(rec["variant"]):
        probs.append("appended text")
    for n, h in enumerate(rec["request_sha256"]):
        req = json.loads(gzip.open(qdir / rec["run_id"] / f"{h}.json.gz", "rt").read())
        if n == 0 and not _same(req["messages"], built):
            probs.append("saved request != built messages")
        if req.get("model") != "gemini/gemini-3.1-flash-lite" or req.get("temperature") != 1.0 \
                or req.get("max_tokens") != 64000 or req.get("reasoning_effort") != "high":
            probs.append(f"params {req.get('model')} {req.get('temperature')} {req.get('max_tokens')} "
                         f"{req.get('reasoning_effort')}")
        tc = req.get("tool_choice")
        if not (isinstance(tc, dict) and tc.get("function", {}).get("name") == "submit_verdict"):
            probs.append(f"tool_choice {tc}")
    if mode == "live" and rec.get("response_models") != ["gemini-3.1-flash-lite"]:
        probs.append(f"response_models {rec.get('response_models')}")
    return probs


def error_note(u: dict) -> str:
    if u["kind"] == "COM":
        b = load_bait(u["item_id"])
        return f"bait: {b['bait_id']} | {b['bait_sentence']}"
    return f"removed: {u['o']['removed_id']} | {u['o']['removed_sentence']}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=L.PARTS, default="first")
    ap.add_argument("--mode", default="live", choices=["live", "mock"])
    ap.add_argument("--checks-only", action="store_true")
    a = ap.parse_args(argv)
    rdir, qdir = DIRS[a.mode]
    want = [j.call_id(L.STAGE) for j in L.part_jobs(a.part)]
    seen = {}
    for r in iter_call_lines(rdir):
        if r.get("stage") == L.STAGE and r.get("mode") == a.mode:
            seen[r["call_id"]] = r
    units = {(u["kind"], u["item_id"]): u for u in L.units()}
    n_probs, n_done = 0, 0
    for cid in want:
        r = seen.get(cid)
        if r is None:
            print(f"== {cid}  NOT LOGGED")
            continue
        n_done += 1
        probs = check_call(r, units, qdir, a.mode)
        n_probs += len(probs)
        if a.checks_only and not probs:
            continue
        print(f"== {cid}  verdict={r.get('verdict')} status={r.get('verdict_status')} "
              f"api_requests={r.get('n_api_requests')} cost={r.get('cost_usd')} problems={probs or 0}")
        if not a.checks_only:
            print(f"   {error_note(units[(r['check'], r['item_id'])])}")
            print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# logged {n_done}/{len(want)}; request problems {n_probs}")


if __name__ == "__main__":
    main()
