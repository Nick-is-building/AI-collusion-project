"""Reading aid for A13 live calls (plan 23.3): checks every saved request against its variant definition and
prints each verdict with its reasoning for reading by hand. Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a13.read_stage --stage1 > scratch/a13/stage1_read.txt
  PYTHONPATH=. .venv/bin/python -m scripts.a13.read_stage --checks-only        # all logged a13 calls
Checks per call: the saved request messages equal the job's built messages (canonical JSON); structure from the
stored trace, independent of the launcher's builder: R2 = stored system prompt + current episode up to Bob's
round-1 message + verdict prompt; R3 = cut context minus every earlier communication phase (one communication
opening left); R4n = fixed neutral system prompt + R4's other 3 messages; R5 = R4 with one user message of Darwin
filler (the matched length) before the communication opening; Bob's round-1 message = the omission content
(omission) or his original message (correct); model, temperature 1.0, max_tokens 64,000, reasoning_effort high,
forced submit_verdict; response_model.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from scripts.a13 import launch_ladder as L
from src.replay.r5 import filler_text
from src.replay.r5_a13 import lookup, omission_items
from src.replay.request import canonical_json
from src.replay.variants import R4N_SYSTEM_PROMPT, _is_comm_opening, build, load_item
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]


def _same(a, b):
    return canonical_json(a) == canonical_json(b)


def structure(msgs: list, o: dict, variant: str, version: str) -> list[str]:
    ctx = load_item(o["trace"], int(o["ep_index"]))
    m = ctx.messages
    bob = o["bob_r1_content"] if version == "omission" else m[ctx.cut_idx]["content"]
    probs = []
    if sum(x.get("content") == bob for x in msgs) != 1:
        probs.append("Bob's round-1 message not exactly once")
    if version == "omission" and any(x.get("content") == m[ctx.cut_idx]["content"] for x in msgs):
        probs.append("original Bob message in an omission cell")
    if not _same(msgs[-1], m[ctx.verdict_prompt_idx]):
        probs.append("last message is not the stored verdict prompt")
    n_open = sum(_is_comm_opening(x) for x in msgs)
    if variant == "R2":
        if not (_same(msgs[0], m[0]) and len(msgs) == 1 + (ctx.cut_idx - ctx.ep_start + 1) + 1
                and _same(msgs[1:-2], m[ctx.ep_start:ctx.cut_idx]) and n_open == 1):
            probs.append("R2 structure")
    elif variant == "R3":
        drop = sum(ctx.verdict_prompt_of(k) - ctx.comm_opening_idx(k) for k in range(ctx.ep_index))
        if not (len(msgs) == ctx.cut_idx + 2 - drop and n_open == 1 and _same(msgs[0], m[0])):
            probs.append("R3 structure")
    elif variant == "R4n":
        if not (msgs[0] == {"role": "system", "content": R4N_SYSTEM_PROMPT} and len(msgs) == 4 and n_open == 1):
            probs.append("R4n structure")
    elif variant == "R5":
        r4 = build(ctx, "R4", bob_r1_content=o["bob_r1_content"] if version == "omission" else None)
        n = lookup()[(o["item_id"], version)]
        if not (len(msgs) == 5 and _same([msgs[0]] + msgs[2:], r4) and msgs[1] == {"role": "user", "content": filler_text(n)}):
            probs.append("R5 structure")
    return probs


def check_call(rec: dict, o: dict) -> list[str]:
    probs = []
    built = L.build_messages(o, rec["variant"], rec["version"])
    for n, h in enumerate(rec["request_sha256"]):
        req = json.loads(gzip.open(ROOT / "results" / "requests" / rec["run_id"] / f"{h}.json.gz", "rt").read())
        if n == 0:
            if not _same(req["messages"], built):
                probs.append("saved request != built messages")
            probs += structure(req["messages"], o, rec["variant"], rec["version"])
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
    ap.add_argument("--checks-only", action="store_true")
    a = ap.parse_args(argv)
    js = L.first_jobs() if a.stage1 else L.jobs()
    want = {j.call_id("a13") for j in js}
    recs = {r["call_id"]: r for r in iter_call_lines(ROOT / "results" / "raw")
            if r.get("stage") == "a13" and r.get("mode") == "live" and r["call_id"] in want}
    om = {o["item_id"]: o for o in omission_items()}
    n_probs = 0
    for cid in [j.call_id("a13") for j in js]:
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
        print(f"== {cid}  verdict={r['verdict']} status={r['verdict_status']} api_requests={r['n_api_requests']} "
              f"problems={probs or 0}")
        print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
        print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# calls expected {len(want)}, logged {len(recs)}, request problems {n_probs}")


if __name__ == "__main__":
    main()
