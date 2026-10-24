"""Hand-reading aid for the first complete calls per variant (plan 23.3; A04 task 3).

For the first N complete main-run calls per variant (in completion order), prints what the request
contained (message count, role sequence summary, system prompt start, which Bob round-1 message is
present (bait / original / none), filler, verdict-prompt tail, tools and the itemization field,
tool_choice) and what came back (number of API requests, response_model, the verdict tool call and
the start of its reasoning). It is a reading aid; it computes no rate or contrast (D18).

  .venv/bin/python -m scripts.main.read_first [--n 5] [--variant R1]
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from scripts.main.monitor import read
from src.runner.item_lists import load_bait
from src.runner.jobs import original_bob_message

ROOT = Path(__file__).resolve().parents[2]


def _req(run_id, h):
    p = ROOT / "results" / "requests" / run_id / f"{h}.json.gz"
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def describe(c: dict, trace_of: dict) -> str:
    req = _req(c["run_id"], c["request_sha256"][0])
    msgs = req["messages"]
    roles = "".join({"system": "S", "user": "u", "assistant": "a", "tool": "t"}[m["role"]] for m in msgs)
    bob = [m for m in msgs if m["role"] == "user" and str(m.get("content", "")).startswith("[round=1/5][from=bob]")]
    which = "none"
    if bob:
        item = c["item_id"]
        try:
            b = load_bait(item)
            if bob[-1]["content"] == b["bob_r1_content"]:
                which = "BAIT"
        except Exception:
            pass
        if which == "none" and item in trace_of:
            tr, ep = trace_of[item]
            if bob[-1]["content"] == original_bob_message(tr, ep)[0]:
                which = "original"
        which = which if which != "none" else "other"
    filler = any(m["role"] == "user" and str(m.get("content", "")).startswith("INTRODUCTION.") for m in msgs)
    tools = [t["function"]["name"] for t in req.get("tools", [])]
    item_field = any("itemization" in t["function"]["parameters"]["properties"] for t in req.get("tools", []))
    out = [f"{c['call_id']}  msgs={len(msgs)} roles={roles[:12]}..{roles[-6:]} sys='{str(msgs[0]['content'])[:50]}'",
           f"   bob_r1={which} filler={filler} tools={tools} itemization_field={item_field} "
           f"tool_choice={json.dumps(req.get('tool_choice'))[:60]} n_api={c['n_api_requests']} models={c['response_models']}",
           f"   verdict_prompt_tail='{str(msgs[-1]['content'])[-120:]}'",
           f"   status={c['verdict_status']} forced={c['forced']} verdict={c['verdict']} reasoning='{(c.get('reasoning') or '')[:300]}'"]
    if c["variant"] == "R6":
        r6 = (c.get("extra") or {}).get("r6", {})
        out.append(f"   r6 first={r6.get('first_verdict')} present={(r6.get('first_check') or {}).get('present')} "
                   f"compliant={(r6.get('first_check') or {}).get('compliant')} gate={r6.get('gate_fired')} final={r6.get('final_verdict')}")
    return "\n".join(out)


def main(argv=None):
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--variant", default=None)
    a = ap.parse_args(argv)
    calls, _ = read()
    calls.sort(key=lambda c: c["ts_end_utc"])
    items = pd.concat([pd.read_csv(ROOT / "data/derived/items" / f) for f in
                       ("candidates.csv", "natural_error_set.csv", "fidelity_set.csv")])
    trace_of = {r.item_id: (r.trace, int(r.ep_index)) for r in items.itertuples()}
    seen = {}
    for c in calls:
        v = c["variant"]
        if (a.variant and v != a.variant) or seen.get(v, 0) >= a.n:
            continue
        seen[v] = seen.get(v, 0) + 1
        print(describe(c, trace_of))


if __name__ == "__main__":
    main()
