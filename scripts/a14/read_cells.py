"""Reading aid for A14 live calls (plan 23.3; A14 step 4): for the first N complete calls of every cell (in log
order), checks the saved request against the cell definition and prints each verdict with its reasoning for
reading by hand. Prints no rate.

  PYTHONPATH=. .venv/bin/python -m scripts.a14.read_cells [--n 5] [--mode live] > scratch/a14/first5_read.txt
  PYTHONPATH=. .venv/bin/python -m scripts.a14.read_cells --ready     # exit 0 iff every cell has N complete calls
Checks per call: the first saved request's messages equal the job's built messages (canonical JSON); relative to
the base context (LOOK: R1-om / R0' (cut) or R4-om; NAT: the N1 context) the cell differs only in the final
verdict prompt, by the exact note block (VIG, CHK, R4+VIG) or by R6x's prompt sentence (R6x), and not at all
(N1f); the verdict tool schema has `source_classification` exactly in R6x calls; model, temperature 1.0,
max_tokens 64,000, reasoning_effort high, forced submit_verdict; response_model.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import sys
from pathlib import Path

from scripts.a06.launch_addendum import omission_items
from scripts.a14 import launch_a14 as L
from scripts.a14.nat_records import nat_items
from src.replay import a14, r6x
from src.replay.request import canonical_json
from src.replay.variants import build, load_item
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
DIRS = {"live": (ROOT / "results" / "raw", ROOT / "results" / "requests"),
        "mock": (ROOT / "logs" / "mock_runs" / "raw", ROOT / "logs" / "mock_runs" / "requests")}


def _same(a, b):
    return canonical_json(a) == canonical_json(b)


def cell_of(rec: dict) -> str:
    return f"{rec['variant']}|{rec['version']}"


def expected(rec: dict, om: dict, nat: dict) -> tuple[list, list, str]:
    """(built messages, base messages, expected last-message suffix)."""
    if rec["check"] == "LOOK":
        o = om[rec["item_id"]]
        base_name, arm = L.LOOK_BASE[rec["variant"]]
        bob = o["bob_r1_content"] if rec["version"] == "omission" else None
        base = build(load_item(o["trace"], int(o["ep_index"])), base_name, bob_r1_content=bob)
        return L.look_messages(o, rec["variant"], rec["version"]), base, "\n\n" + a14.note_block(arm)
    row = nat[rec["item_id"]]
    base = build(load_item(row.trace, int(row.ep_index)), "CUT")
    suffix = " " + r6x.PROMPT_SENTENCE if rec["variant"] == "R6x" else ""
    return L.nat_messages(row.trace, int(row.ep_index), rec["variant"]), base, suffix


def check_call(rec: dict, om: dict, nat: dict, qdir: Path) -> list[str]:
    probs = []
    built, base, suffix = expected(rec, om, nat)
    diff = [i for i in range(len(base)) if not _same(built[i], base[i])]
    if len(built) != len(base) or diff != ([len(base) - 1] if suffix else []):
        probs.append(f"diff positions {diff}")
    if suffix and not built[-1]["content"].endswith(suffix):
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
        sv = [t for t in req.get("tools") or [] if t["function"]["name"] == "submit_verdict"]
        has = bool(sv) and r6x.FIELD in sv[0]["function"]["parameters"]["properties"]
        if has != (rec["variant"] == "R6x"):
            probs.append(f"schema field present={has}")
    if rec.get("response_models") != ["gemini-3.1-flash-lite"] and rec.get("mode") == "live":
        probs.append(f"response_models {rec.get('response_models')}")
    return probs


def first_calls(mode: str, n: int) -> dict:
    rdir = DIRS[mode][0]
    by = collections.defaultdict(list)
    for r in iter_call_lines(rdir):
        if r.get("stage") == "a14" and r.get("mode") == mode and r.get("verdict_status") == "ok":
            if len(by[cell_of(r)]) < n:
                by[cell_of(r)].append(r)
    return by


CELLS = ["VIG|omission", "VIG|correct", "CHK|omission", "CHK|correct", "R4+VIG|omission", "N1f|natural", "R6x|natural"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--mode", default="live", choices=["live", "mock"])
    ap.add_argument("--ready", action="store_true")
    a = ap.parse_args(argv)
    by = first_calls(a.mode, a.n)
    if a.ready:
        sys.exit(0 if all(len(by[c]) >= a.n for c in CELLS) else 1)
    om = {o["item_id"]: o for o in omission_items()}
    nat = {r.item_id: r for r in nat_items().itertuples()}
    recs = __import__("pandas").read_csv(ROOT / "data" / "derived" / "a14" / "nat_records.csv", keep_default_na=False)
    n_probs = 0
    for c in CELLS:
        print(f"\n######## {c}: {len(by[c])} calls")
        for r in by[c]:
            probs = check_call(r, om, nat, DIRS[a.mode][1])
            n_probs += len(probs)
            print(f"== {r['call_id']}  verdict={r['verdict']} api_requests={r['n_api_requests']} problems={probs or 0}")
            if r["check"] == "LOOK":
                o = om[r["item_id"]]
                print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
            else:
                for x in recs[recs.item_id == r["item_id"]].itertuples():
                    print(f"   {x.role}: {x.record_id} | {x.sentence}")
                s = (r.get("extra") or {}).get("r6x")
                if s:
                    ch = s.get("first_check") or {}
                    labs = {x.record_id: r6x.label_of(s.get("first_classification"), x.sentence)
                            for x in recs[recs.item_id == r["item_id"]].itertuples() if x.sentence}
                    print(f"   R6x first={s.get('first_verdict')} final={s.get('final_verdict')} "
                          f"compliant={ch.get('compliant')} gate_fired={s.get('gate_fired')} labels={labs}")
            print("   " + (r.get("reasoning") or "").replace("\n", "\n   "))
    print(f"\n# request problems {n_probs}")


if __name__ == "__main__":
    main()
