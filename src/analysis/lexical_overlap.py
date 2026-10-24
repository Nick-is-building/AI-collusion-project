"""Deterministic lexical overlap between an extraction record and the instruction's exclusion clause
(A06, D24). Computed for the natural-error records (missing and extra) and for our extraction baits.

Definition (the same word rule the bait builder uses, `baits_extraction._words`):
  words(s)  = {first 5 letters of every lowercase alphabetic token of length >= 4, stop words removed}
  E         = words(text after the first "Exclude"/"exclude") - words(text before it)
  overlap   = words(record sentence) & E
  reported: overlap_n = |overlap|, overlap_words, excl_n = |E|, overlap_share = overlap_n / excl_n.
Not applicable (row kept, values empty, reason given): data-search and code-analysis items (no record
sentence; data-search prompts have no exclusion clause), and record IDs that are not in the task's
source (e.g. a mistyped ID). Extraction baits were *selected* to have overlap >= 1 (D7), so their
values are not comparable to natural errors as a random sample; the table reports them side by side.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.replay.baits_extraction import _words, manifest, source_lines
from src.replay.traces import load_trace

ROOT = Path(__file__).resolve().parents[2]
NATURAL = ROOT / "data" / "derived" / "items" / "natural_error_set.csv"
BAITS = ROOT / "data" / "derived" / "baits"
OUT = ROOT / "data" / "derived" / "rubric" / "lexical_overlap.csv"


def exclusion_words(instruction: str) -> set:
    m = re.search(r"\b[Ee]xclude\b(.*)$", instruction)
    if not m:
        return set()
    return _words(m.group(1)) - _words(instruction[:m.start()])


def overlap(task_id: str, sentence: str) -> dict:
    e = exclusion_words(manifest()[task_id]["extraction_instruction"])
    ov = sorted(_words(sentence) & e)
    return dict(overlap_n=len(ov), overlap_words=" ".join(ov), excl_n=len(e),
                overlap_share=round(len(ov) / len(e), 4) if e else None)


def natural_rows() -> list[dict]:
    rows = []
    for r in pd.read_csv(NATURAL).itertuples():
        base = dict(source="natural_error", set=r.set, item_id=r.item_id, task_type=r.task_type,
                    task_id=r.peer_task_id, error_type=r.error_type)
        if r.task_type != "record_extraction":
            rows.append(base | dict(record_role="", record_id="", applicable=False,
                                    reason="no record sentence / no exclusion clause"))
            continue
        ev = load_trace(r.trace)["results"][int(r.ep_index)]["agents"]["bob"]["extraction_eval"]
        lines = dict(source_lines(r.peer_task_id))
        for role, key in (("missing", "missing_references"), ("extra", "extra_references")):
            for rid in ev[key]:
                if rid not in lines:
                    rows.append(base | dict(record_role=role, record_id=rid, applicable=False,
                                            reason="record ID not in the task source"))
                    continue
                rows.append(base | dict(record_role=role, record_id=rid, applicable=True, reason="",
                                        sentence=lines[rid]) | overlap(r.peer_task_id, lines[rid]))
    return rows


def bait_rows() -> list[dict]:
    rows = []
    for p in sorted(BAITS.glob("rep*_alice.json")):
        b = json.loads(p.read_text())
        base = dict(source="bait", set=b["set"], item_id=b["item_id"], task_type=b["task_type"],
                    task_id=b["task_id"], error_type="commission", record_role="extra")
        if b["task_type"] != "record_extraction":
            rows.append(base | dict(record_id="", applicable=False,
                                    reason="data-search bait: relaxed SQL condition, no record sentence"))
            continue
        rows.append(base | dict(record_id=b["bait_id"], applicable=True, reason="",
                                sentence=b["bait_sentence"]) | overlap(b["task_id"], b["bait_sentence"]))
    return rows


def table() -> pd.DataFrame:
    cols = ["source", "set", "item_id", "task_type", "task_id", "error_type", "record_role", "record_id",
            "applicable", "reason", "overlap_n", "overlap_words", "excl_n", "overlap_share", "sentence"]
    return pd.DataFrame(natural_rows() + bait_rows()).reindex(columns=cols)


def main():
    t = table()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT, index=False)
    a = t[t.applicable]
    print(f"{len(t)} rows ({len(a)} applicable) -> {OUT.relative_to(ROOT)}")
    print(a.groupby(["source", "record_role"]).overlap_n.agg(["count", "mean", "median", "min", "max"]))


if __name__ == "__main__":
    main()
