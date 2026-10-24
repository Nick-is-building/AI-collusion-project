"""Build, validate and save baits for all candidates; write the item flow (plan sections 8.3, 23.4).

Outputs (committed):
  data/derived/baits/<item_id>.json   one validated bait: bob_r1_content (+ SHA-256), bait_raw_log, bait record,
                                      edits, evaluator result, validation rules 1-3, count mode
  data/derived/baits/diffs/<item_id>.diff   unified diff of the raw log and of Bob's framing text
  data/derived/baits/item_flow.csv    every candidate: built / validated / drop reason

Record extraction: src/replay/baits_extraction.py. Data search: not built -- in 0 of 101
candidates does Bob's answer query return any column besides the key, so no relaxation can add a
row "whose violating value is visible in the result columns" (plan 8.3); see devlog 03, task 6.

Usage: .venv/bin/python -m src.replay.build_baits [--count-mode plan_nouns|any_noun]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.replay.bait_common import COUNT_MODES, Ambiguous
from src.replay.baits_extraction import build_bait, diff_text, validate

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "derived" / "items" / "candidates.csv"
OUT = ROOT / "data" / "derived" / "baits"
DATA_SEARCH_DROP = "data search: answer query returns only the key column; no visible violating value (plan 8.3)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count-mode", default="plan_nouns", choices=COUNT_MODES)
    args = ap.parse_args()
    (OUT / "diffs").mkdir(parents=True, exist_ok=True)
    for f in list(OUT.glob("*.json")) + list((OUT / "diffs").glob("*.diff")):
        f.unlink()  # derived outputs, fully regenerated from the traces
    flow = []
    for r in pd.read_csv(ITEMS).itertuples():
        row = dict(item_id=r.item_id, set=r.set, task_type=r.task_type, built=False, validated=False, reason="")
        if r.task_type != "record_extraction":
            row["reason"] = DATA_SEARCH_DROP
            flow.append(row)
            continue
        try:
            b = build_bait(r.trace, r.ep_index, args.count_mode)
        except Ambiguous as e:
            row["reason"] = str(e)
            flow.append(row)
            continue
        v = validate(b, r.trace, r.ep_index)
        row.update(built=True, validated=all(v.values()), reason="" if all(v.values()) else f"failed {v}")
        flow.append(row)
        if not all(v.values()):
            continue
        rec = dict(item_id=r.item_id, set=r.set, task_type=r.task_type, trace=r.trace, ep_index=r.ep_index,
                   task_id=b["task_id"], bait_id=b["bait_id"], bait_sentence=b["bait_sentence"],
                   overlap_words=b["overlap_words"], answer_size=b["answer_size"], count_mode=args.count_mode,
                   edits=b["edits"], evaluator=b["evaluator"], validation=v,
                   bob_r1_content=b["bob_r1_content"], bait_raw_log=b["new_raw_log"],
                   bob_r1_content_sha256=hashlib.sha256(b["bob_r1_content"].encode()).hexdigest(),
                   original_bob_r1_content_sha256=hashlib.sha256(b["original_bob_r1_content"].encode()).hexdigest())
        (OUT / f"{r.item_id}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
        (OUT / "diffs" / f"{r.item_id}.diff").write_text(diff_text(b))
    flow = pd.DataFrame(flow)
    flow.to_csv(OUT / "item_flow.csv", index=False)
    print(f"count mode: {args.count_mode}")
    print(flow.groupby(["task_type", "set"]).agg(candidates=("item_id", "size"), built=("built", "sum"),
                                                 validated=("validated", "sum")).to_string())


if __name__ == "__main__":
    main()
