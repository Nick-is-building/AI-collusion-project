"""Reading aid for A10 live calls (plan 23.3): checks every saved request of the given call lines against its
cell definition and prints each verdict with its reasoning for reading by hand. Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a10.read_stage --stage1 [--optional] > scratch/a10/stage1_read.txt
Checks per call: the saved request messages equal the job's built messages (canonical JSON); relative to the
base context (R1-om / R0'), INC arms differ only in the verdict prompt (by the exact block), SIG arms only in
Bob's round-1 message (by the exact signal), the combo cell in exactly those two; model, temperature 1.0,
max_tokens 64,000, reasoning_effort high, forced submit_verdict; response_model; API requests per call.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from scripts.a06.launch_addendum import omission_items
from scripts.a10 import launch_a10 as L
from src.replay import a10
from src.replay.request import canonical_json
from src.replay.variants import build, load_item
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]


def _same(a, b):
    return canonical_json(a) == canonical_json(b)


def check_call(rec: dict, o: dict) -> list[str]:
    probs = []
    built = L.build_messages(o, rec["variant"], rec["version"])
    base = build(load_item(o["trace"], int(o["ep_index"])), "CUT",
                 bob_r1_content=o["bob_r1_content"] if rec["version"] == "omission" else None)
    k = load_item(o["trace"], int(o["ep_index"])).cut_idx
    reward, signal = a10.arm_parts(rec["variant"])
    expect = ([k] if signal else []) + ([len(base) - 1] if reward else [])
    diff = [i for i in range(len(base)) if not _same(built[i], base[i])]
    if len(built) != len(base) or diff != expect:
        probs.append(f"diff positions {diff} != {expect}")
    if reward and not built[-1]["content"].endswith("\n\n" + a10.reward_block(reward)):
        probs.append("reward block")
    if signal and not built[k]["content"].endswith("\n\n" + a10.PEER_SIGNALS[signal]):
        probs.append("peer signal")
    for n, h in enumerate(rec["request_sha256"]):
        p = ROOT / "results" / "requests" / rec["run_id"] / f"{h}.json.gz"
        req = json.loads(gzip.open(p, "rt").read())
        if n == 0 and not _same(req["messages"], built):
            probs.append("saved request != built messages")
        if req.get("model") != "gemini/gemini-3.1-flash-lite" or req.get("temperature") != 1.0 \
                or req.get("max_tokens") != 64000 or req.get("reasoning_effort") != "high":
            probs.append(f"params {req.get('model')} {req.get('temperature')} {req.get('max_tokens')} "
                         f"{req.get('reasoning_effort')}")
        tc = req.get("tool_choice")
        if not (isinstance(tc, dict) and tc.get("function", {}).get("name") == "submit_verdict"):
            probs.append(f"tool_choice {tc}")
    if rec.get("response_models") != ["gemini-3.1-flash-lite"]:
        probs.append(f"response_models {rec.get('response_models')}")
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", action="store_true")
    ap.add_argument("--optional", action="store_true")
    a = ap.parse_args(argv)
    js = (L.optional_first_jobs() if a.optional else L.first_jobs()) if a.stage1 else \
        (L.optional_jobs() if a.optional else L.jobs())
    want = {j.call_id("a10") for j in js}
    recs = {r["call_id"]: r for r in iter_call_lines(ROOT / "results" / "raw")
            if r.get("stage") == "a10" and r.get("mode") == "live" and r["call_id"] in want}
    om = {o["item_id"]: o for o in omission_items()}
    n_probs = 0
    for cid in [j.call_id("a10") for j in js]:
        r = recs.get(cid)
        if r is None:
            print(f"== {cid}: NOT LOGGED")
            continue
        probs = check_call(r, om[r["item_id"]])
        n_probs += len(probs)
        o = om[r["item_id"]]
        print(f"== {cid}  verdict={r['verdict']} status={r['verdict_status']} api_requests={r['n_api_requests']} "
              f"problems={probs or 0}")
        print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
        print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# calls expected {len(want)}, logged {len(recs)}, request problems {n_probs}")


if __name__ == "__main__":
    main()
