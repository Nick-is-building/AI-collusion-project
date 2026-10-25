"""A14 task 2: table of the natural errors' missing and extra records (written and committed before any A14 call).

Items: the 26 record-extraction items of the preregistered natural-error set (data/derived/items/
natural_error_set.csv; 19 omission, 3 commission, 4 both). Per item, from Shi et al.'s evaluator result in the
trace (agents.bob.extraction_eval: missing_references, extra_references) and the task's source file
(src.replay.baits_extraction.source_lines: record ID -> sentence), one row per missing or extra record:
  role (missing / extra), record_id, sentence ("" if the ID is not in the task source), in_task_source,
  in_transmitted_read_source = the sentence (outer whitespace stripped) equals one source sentence of Bob's
  transmitted read_source result (src.replay.r6x.source_sentences of his original raw log; the same equality the
  R6x gate and label rule use). Rows that fail either check are flagged, counted and kept (A14: do not drop).
Also d24_decidable (data/derived/rubric/natural_error_decidability.csv) and the trajectory (cluster).
Output: data/derived/a14/nat_records.csv and its SHA-256 in data/derived/a14/nat_records.sha256.
Fails if the item count is not 26 (19/3/4) or if R6x cannot be built for an item (no single read_source call).

  PYTHONPATH=. .venv/bin/python -m scripts.a14.nat_records
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.replay.baits_extraction import source_lines
from src.replay.r6x import source_sentences
from src.replay.traces import load_trace
from src.runner.jobs import original_bob_message

ROOT = Path(__file__).resolve().parents[2]
NATURAL = ROOT / "data" / "derived" / "items" / "natural_error_set.csv"
D24 = ROOT / "data" / "derived" / "rubric" / "natural_error_decidability.csv"
OUT = ROOT / "data" / "derived" / "a14" / "nat_records.csv"
EXPECTED = {"omission": 19, "commission": 3, "both": 4}


def nat_items() -> pd.DataFrame:
    nat = pd.read_csv(NATURAL)
    ext = nat[nat.task_type == "record_extraction"].reset_index(drop=True)
    counts = ext.error_type.value_counts().to_dict()
    if len(ext) != 26 or counts != EXPECTED:
        raise RuntimeError(f"natural extraction items: {len(ext)} {counts}, expected 26 {EXPECTED}")
    return ext


def build_table() -> pd.DataFrame:
    d24 = pd.read_csv(D24).set_index("item_id")["decidable"]
    rows = []
    for r in nat_items().itertuples():
        ep = int(r.ep_index)
        ev = load_trace(r.trace)["results"][ep]["agents"]["bob"]["extraction_eval"]
        _, raw = original_bob_message(r.trace, ep)
        transmitted = {s.strip() for s in source_sentences(raw)}   # raises if R6x cannot be built
        lines = dict(source_lines(r.peer_task_id))
        for role, key in (("missing", "missing_references"), ("extra", "extra_references")):
            for rid in ev[key]:
                sent = lines.get(rid)
                rows.append(dict(item_id=r.item_id, cluster=r.trace.split(".")[0], ep_index=ep,
                                 task_id=r.peer_task_id, error_type=r.error_type, d24_decidable=d24[r.item_id],
                                 role=role, record_id=rid, sentence=sent or "", in_task_source=sent is not None,
                                 in_transmitted_read_source=sent is not None and sent.strip() in transmitted))
    return pd.DataFrame(rows)


def main():
    t = build_table()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT, index=False)
    h = hashlib.sha256(OUT.read_bytes()).hexdigest()
    OUT.with_suffix(".sha256").write_text(f"{h}  {OUT.relative_to(ROOT)}\n")
    flagged = t[~(t.in_task_source & t.in_transmitted_read_source)]
    print(f"{t.item_id.nunique()} items, {len(t)} records (missing {int((t.role == 'missing').sum())}, "
          f"extra {int((t.role == 'extra').sum())}); flagged {len(flagged)}: "
          f"{flagged[['item_id', 'role', 'record_id']].values.tolist()}; sha256 {h}")


if __name__ == "__main__":
    main()
