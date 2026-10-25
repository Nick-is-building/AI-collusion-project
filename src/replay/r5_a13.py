"""R5 fillers for the A13 omission ladder (D36); thin wrapper around the unchanged `src.replay.r5.match_item`.

Rows written to data/derived/r5_fillers_a13.csv (the prereg-v1 table data/derived/r5_fillers.csv is not edited):
  version "omission", all 50 D25 omission items: target = count(cut context with the omission content)
      - count(R4 with the omission content)  (match_item with bob_r1_content = the item file's bob_r1_content);
  version "correct", only the items without a "correct" row in r5_fillers.csv (the 28 omission items outside
      the main list): target = count(R0') - count(R4-correct)  (match_item with bob_r1_content = None).
The 22 main-list items reuse their "correct" rows from r5_fillers.csv (`lookup`).
Matching rule, tolerance (±2%) and countTokens logging (results/token_counts/counts.jsonl, purpose
"r5_filler") are those of src.replay.r5. Resumable: rows already in the output are skipped.

  set -a; . ./.env; set +a
  PYTHONPATH=. nohup .venv/bin/python -m src.replay.r5_a13 --live > logs/a13_r5_match.log 2>&1 &
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.replay.r5 import OUT as PREREG_TABLE, match_item

ROOT = Path(__file__).resolve().parents[2]
OMISSION_DIR = ROOT / "data" / "derived" / "omission_baits"
OUT = ROOT / "data" / "derived" / "r5_fillers_a13.csv"


def omission_items() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(OMISSION_DIR.glob("rep*_alice.json"))]


def _matched(path: Path) -> dict:
    if not path.exists():
        return {}
    d = pd.read_csv(path)
    return {(r.item_id, r.version): int(r.n_chars) for r in d.itertuples() if bool(r.within_tolerance)}


def lookup() -> dict:
    """(item_id, version) -> n_chars for every matched A13 cell: omission rows from r5_fillers_a13.csv;
    correct rows from r5_fillers_a13.csv, else from the prereg-v1 r5_fillers.csv."""
    items = {o["item_id"] for o in omission_items()}
    a13, prereg = _matched(OUT), _matched(PREREG_TABLE)
    out = {}
    for i in items:
        if (i, "omission") in a13:
            out[(i, "omission")] = a13[(i, "omission")]
        n = a13.get((i, "correct"), prereg.get((i, "correct")))
        if n is not None:
            out[(i, "correct")] = n
    return out


def todo() -> list[tuple[dict, str]]:
    prereg_correct = {i for (i, v) in _matched(PREREG_TABLE) if v == "correct"}
    out = []
    for o in omission_items():
        out.append((o, "omission"))
        if o["item_id"] not in prereg_correct:
            out.append((o, "correct"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="countTokens calls for counts not yet cached")
    a = ap.parse_args(argv)
    rows, done = [], set()
    if OUT.exists():
        rows = pd.read_csv(OUT).to_dict("records")
        done = {(r["item_id"], r["version"]) for r in rows}
    for o, version in todo():
        if (o["item_id"], version) in done:
            continue
        content = o["bob_r1_content"] if version == "omission" else None
        res = match_item(o["trace"], int(o["ep_index"]), "record_extraction", o["item_id"], version, content, a.live)
        rows.append(res)
        done.add((o["item_id"], version))
        pd.DataFrame(rows).sort_values(["item_id", "version"]).to_csv(OUT, index=False)
        print(res["item_id"], version, res["target_tokens"], res["filler_tokens"], f"{res['rel_error']:+.4f}",
              res["within_tolerance"], flush=True)
    d = pd.DataFrame(rows)
    print(f"A13 R5 fillers: {len(d)} rows, within ±2%: {int(d.within_tolerance.sum())}; "
          f"matched A13 cells (incl. reused prereg-v1 correct rows): {len(lookup())}")


if __name__ == "__main__":
    main()
