"""Reading aid for A15 live calls (plan 23.3): checks every saved request against its cell and prints each verdict
with its reasoning for reading by hand. Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a15.read_stage --stage1 > scratch/a15/stage1_read.txt
  PYTHONPATH=. .venv/bin/python -m scripts.a15.read_stage --checks-only        # all logged a15 calls
Checks per call: saved request messages == the cell's built messages (canonical JSON); built from R3 of the stored trace:
the request is an in-order subsequence of R3 (per-message SHA-256) that lacks exactly the variant's earlier segments
(R3t: every earlier outcome segment, R3o: every earlier task phase); the earlier-episode headings present are those
the variant claims; the current episode equals R1's; Bob's message is the omission content (omission) or his original
message (correct); model, temperature 1.0, max_tokens 64,000, reasoning_effort high, forced submit_verdict;
response_model.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from scripts.a15 import launch_a15 as L
from src.replay.r3_history import segments
from src.replay.r5_a13 import omission_items
from src.replay.request import canonical_json
from src.replay.variants import build, load_item
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]


def _h(m):
    return hashlib.sha256(canonical_json(m).encode()).hexdigest()


def structure(msgs: list, o: dict, variant: str, version: str) -> list[str]:
    ctx = load_item(o["trace"], int(o["ep_index"]))
    m = ctx.messages
    content = o["bob_r1_content"] if version == "omission" else None
    r1, r3 = build(ctx, "CUT", content), build(ctx, "R3", content)
    hm, h3 = [_h(x) for x in msgs], [_h(x) for x in r3]
    probs = []
    it = iter(h3)
    if not all(x in it for x in hm):
        probs.append("not an in-order subsequence of R3")
    seg = "outcome" if variant == "R3t" else "task"
    exp = sum(e - s for s, e in (segments(ctx, k)[seg] for k in range(ctx.ep_index)))
    if len(r3) - len(msgs) != exp:
        probs.append(f"removed {len(r3) - len(msgs)} messages, expected {exp}")
    n_cur = ctx.cut_idx - ctx.ep_start + 2
    if hm[-n_cur:] != [_h(x) for x in r1[-n_cur:]]:
        probs.append("current episode differs from R1")
    bob = content if content is not None else m[ctx.cut_idx]["content"]
    if msgs[-2].get("content") != bob:
        probs.append("Bob's round-1 message")
    texts = [str(x.get("content") or "") for x in msgs[:-n_cur]]
    for k in range(ctx.ep_index):
        task = any(t.startswith(f"## Episode {k + 1}: task phase") for t in texts)
        outc = any(t.startswith(f"Episode {k + 1} complete") for t in texts)
        if (variant == "R3t" and not (task and not outc)) or (variant == "R3o" and not (outc and not task)):
            probs.append(f"ep{k + 1}: task phase {task}, outcome {outc}")
    return probs


def check_call(rec: dict, o: dict) -> list[str]:
    probs = []
    built = L.build_messages(o, rec["variant"], rec["version"])
    for n, h in enumerate(rec["request_sha256"]):
        req = json.loads(gzip.open(ROOT / "results" / "requests" / rec["run_id"] / f"{h}.json.gz", "rt").read())
        if n == 0:
            if canonical_json(req["messages"]) != canonical_json(built):
                probs.append("saved request != built messages")
            probs += structure(req["messages"], o, rec["variant"], rec["version"])
        if req.get("model") != "gemini/gemini-3.1-flash-lite" or req.get("temperature") != 1.0 \
                or req.get("max_tokens") != 64000 or req.get("reasoning_effort") != "high":
            probs.append("params")
        tc = req.get("tool_choice")
        if not (isinstance(tc, dict) and tc.get("function", {}).get("name") == "submit_verdict"):
            probs.append(f"tool_choice {tc}")
    if rec.get("response_models") != ["gemini-3.1-flash-lite"]:
        probs.append(f"response_models {rec.get('response_models')}")
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", action="store_true")
    ap.add_argument("--checks-only", action="store_true")
    a = ap.parse_args(argv)
    js = L.first_jobs() if a.stage1 else L.jobs()
    want = [j.call_id("a15") for j in js]
    recs = {r["call_id"]: r for r in iter_call_lines(ROOT / "results" / "raw")
            if r.get("stage") == "a15" and r.get("mode") == "live" and r["call_id"] in set(want)}
    om = {o["item_id"]: o for o in omission_items()}
    n_probs = 0
    for cid in want:
        r = recs.get(cid)
        if r is None:
            if not a.checks_only:
                print(f"== {cid}: NOT LOGGED")
            continue
        o = om[r["item_id"]]
        probs = check_call(r, o)
        n_probs += len(probs)
        if a.checks_only:
            if probs:
                print(f"== {cid} problems={probs}")
            continue
        tok = next((u["input_tokens"] for u in r.get("usage") or [] if not u.get("error_category")), None)
        print(f"== {cid}  verdict={r['verdict']} status={r['verdict_status']} input_tokens={tok} problems={probs or 0}")
        print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
        print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# calls expected {len(want)}, logged {len(recs)}, request problems {n_probs}")


if __name__ == "__main__":
    main()
