"""Reading aid for A17 live calls (plan 23.3): for the given part, checks every saved request against its cell and
prints each verdict with its reasoning for reading by hand. Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a17.read_stage --part first > scratch/a17/stage1_read.txt
Checks per call: the first saved (upstream) request's messages equal the cell's built messages (canonical JSON) and
its parameters are the Flash-Lite ones (the request the converter starts from); the converted Anthropic request
(extra.a17) has model anthropic/claude-haiku-5-5, tool_choice auto, adaptive thinking, effort high, no temperature;
every accepted response model is claude-haiku-5-5; thinking blocks on Haiku's turns; tool calls made.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from scripts.a06.launch_addendum import omission_items
from scripts.a17 import launch_a17 as L
from src.replay import a17
from src.replay.a17_cells import build_messages
from src.replay.request import canonical_json
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]


def check(rec, o) -> list[str]:
    probs = []
    built = build_messages(o, rec["variant"], rec["version"])
    h = rec["request_sha256"][0]
    req = json.loads(gzip.open(ROOT / "results" / "requests" / rec["run_id"] / f"{h}.json.gz", "rt").read())
    if canonical_json(req["messages"]) != canonical_json(built):
        probs.append("saved upstream request != built messages")
    if req.get("model") != a17.BUILDER_MODEL or req.get("temperature") != 1.0 or req.get("max_tokens") != 64000:
        probs.append(f"upstream params {req.get('model')} {req.get('temperature')} {req.get('max_tokens')}")
    ars = (rec.get("extra") or {}).get("a17", {}).get("anthropic_requests") or []
    if not ars or any(a is None for a in ars):
        probs.append("no converted-request record")
    for a in ars:
        p = (a or {}).get("params", {})
        if p.get("model") != a17.MODEL_HAIKU or p.get("tool_choice") != "auto" or p.get("thinking") != {"type": "adaptive"} \
                or p.get("reasoning_effort") != "high" or "temperature" in p:
            probs.append(f"anthropic params {p}")
    acc = {u.get("response_model") for u in rec.get("usage") or [] if not u.get("error_category")}
    if acc != {a17.SERVED_MODEL}:
        probs.append(f"response models {acc}")
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["p6", "first", "all"], default="first")
    a = ap.parse_args(argv)
    js = L.PARTS[a.part]()
    want = [j.call_id("a17") for j in js]
    recs = {r["call_id"]: r for r in iter_call_lines(ROOT / "results" / "raw") if r.get("stage") == "a17"
            and r.get("mode") == "live"}
    om = {o["item_id"]: o for o in omission_items()}
    n_probs = 0
    for cid in want:
        r = recs.get(cid)
        if r is None:
            print(f"== {cid}: NOT LOGGED")
            continue
        probs = check(r, om[r["item_id"]])
        n_probs += len(probs)
        msgs = r.get("response_messages") or []
        tools = [tc["function"]["name"] for m in msgs for tc in m.get("tool_calls") or []]
        think = sum(bool(m.get("thinking_blocks")) for m in msgs if m.get("role") == "assistant")
        print(f"== {cid} verdict={r['verdict']} status={r['verdict_status']} api_requests={r['n_api_requests']} "
              f"tools={tools} thinking_turns={think} cost={r['cost_usd']:.4f} problems={probs or 0}")
        o = om[r["item_id"]]
        print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
        print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# calls expected {len(want)}, logged {sum(c in recs for c in want)}, request problems {n_probs}")


if __name__ == "__main__":
    main()
