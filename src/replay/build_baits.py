"""Build, validate and save baits for all candidates; write the item flow (plan sections 8.3, 23.4;
deviations D2-D5, assignment A02).

Outputs (committed):
  data/derived/baits/<item_id>.json   one validated bait: bob_r1_content (+ SHA-256), bait_raw_log, bait
                                      details, edits, evaluator result, validation rules 1-3, count mode
  data/derived/baits/diffs/<item_id>.diff   unified diff of the raw log and of Bob's framing text
  data/derived/baits/item_flow.csv    every candidate: built / validated / drop reason, plus the D2 flag
                                      bob_states_condition (data search), the D4 bait rank (extraction),
                                      and the D5 reason for extraction tasks without an eligible record

Record extraction: src/replay/baits_extraction.py (D3 count rule, D4 bait choice).
Data search: src/replay/baits_data_search.py (D2).

Usage: .venv/bin/python -m src.replay.build_baits [--count-mode answer_noun|plan_nouns|any_noun]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.replay import baits_data_search as ds
from src.replay import baits_extraction as ex
from src.replay.bait_common import COUNT_MODES, Ambiguous, pretty_log, unified_diff
from src.replay.traces import load_trace

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "derived" / "items" / "candidates.csv"
OUT = ROOT / "data" / "derived" / "baits"


def ds_diff_text(b: dict) -> str:
    return (unified_diff(pretty_log(b["original_raw_log"]), pretty_log(b["new_raw_log"]), "raw_log")
            + unified_diff(b["original_bob_r1_content"].replace(b["original_raw_log"], "<RAW_LOG>") + "\n",
                           b["bob_r1_content"].replace(b["new_raw_log"], "<RAW_LOG>") + "\n", "bob_round1_framing"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--count-mode", default="answer_noun", choices=COUNT_MODES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    out = args.out
    (out / "diffs").mkdir(parents=True, exist_ok=True)
    for f in list(out.glob("*.json")) + list((out / "diffs").glob("*.diff")):
        f.unlink()  # derived outputs, fully regenerated from the traces
    flow = []
    for r in pd.read_csv(ITEMS).itertuples():
        row = dict(item_id=r.item_id, set=r.set, task_type=r.task_type, built=False, validated=False, reason="",
                   no_bait_reason="", bait_rank="", bob_states_condition="", bob_states_condition_where="")
        mod = ex if r.task_type == "record_extraction" else ds
        if r.task_type == "record_extraction":
            task_id = load_trace(r.trace)["results"][r.ep_index]["agents"]["bob"]["task_id"]
            row["no_bait_reason"] = ex.no_bait_reason(task_id) or ""
        try:
            b = mod.build_bait(r.trace, r.ep_index, args.count_mode)
        except Ambiguous as e:
            row["reason"] = str(e)
            flow.append(row)
            continue
        v = mod.validate(b, r.trace, r.ep_index)
        row.update(built=True, validated=all(v.values()), reason="" if all(v.values()) else f"failed {v}")
        if r.task_type == "record_extraction":
            row["bait_rank"] = b["bait_rank"]
        else:
            row["bob_states_condition"] = b["bob_states_condition"]
            row["bob_states_condition_where"] = "+".join(b["bob_states_condition_where"])
        flow.append(row)
        if not all(v.values()):
            continue
        rec = dict(item_id=r.item_id, set=r.set, task_type=r.task_type, trace=r.trace, ep_index=r.ep_index,
                   task_id=b["task_id"], bait_id=b["bait_id"], answer_size=b["answer_size"],
                   count_mode=args.count_mode, edits=b["edits"], evaluator=b["evaluator"], validation=v)
        if r.task_type == "record_extraction":
            rec.update(bait_sentence=b["bait_sentence"], overlap_words=b["overlap_words"],
                       bait_rank=b["bait_rank"], skipped_baits=b["skipped_baits"],
                       right_reason_markers=dict(bait_id=b["bait_id"], bait_sentence=b["bait_sentence"]))
            diff = ex.diff_text(b)
        else:
            rec.update({k: b[k] for k in ("added_key", "added_row", "original_condition", "relaxed_condition",
                                          "condition_kind", "condition_column", "violated_literal", "added_value",
                                          "conjunct_index", "answer_query_seq", "bob_states_condition",
                                          "bob_states_condition_where", "right_reason_markers")})
            diff = ds_diff_text(b)
        rec.update(bob_r1_content=b["bob_r1_content"], bait_raw_log=b["new_raw_log"],
                   bob_r1_content_sha256=hashlib.sha256(b["bob_r1_content"].encode()).hexdigest(),
                   original_bob_r1_content_sha256=hashlib.sha256(b["original_bob_r1_content"].encode()).hexdigest())
        (out / f"{r.item_id}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str) + "\n")
        (out / "diffs" / f"{r.item_id}.diff").write_text(diff)
    flow = pd.DataFrame(flow)
    flow.to_csv(out / "item_flow.csv", index=False)
    print(f"count mode: {args.count_mode}")
    print(flow.groupby(["task_type", "set"]).agg(candidates=("item_id", "size"), built=("built", "sum"),
                                                 validated=("validated", "sum")).to_string())
    return flow


if __name__ == "__main__":
    main()
