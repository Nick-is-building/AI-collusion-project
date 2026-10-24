"""D29 (A07 calls it D28): natural-error tension, EXPLORATORY, no model calls.

N1 (cut workflow context) rejects more natural errors than N4 (isolated R4 context), 10/35 vs 5/35,
the opposite of the D25 planted-omission result (R1-om < R4-om). This script lists the N1/N4-discordant
natural items and describes every missing record (natural omissions, missing records of 'both' items,
and the 50 planted D25 omissions) by deterministic features of Bob's transmitted raw log and the source:

  (a) selected/resolved: the record's sentence in any resolve_records arguments (exact after whitespace
      normalisation, or one containing the other), its ID in any resolve_records result, its ID in any
      save_final_answer answer;
  (b) its sentence verbatim in a read_source result of the transmitted log;
  (c) its position among the task's source records (index, relative position, first/last) and whether
      it lies between two valid records that Bob's final answer includes.
Plus whether Bob's visible text outside the raw log (round-1 framing, saved-answer reasoning) names the
record (D25 naming rule; planted records are never named, by construction), the D24 decidability class and lexical overlap (natural rows), and whether the REJECT reasoning of
each cell (N1/N4 natural; R1/R4 omission planted, per draw) names the record: its ID or a distinctive
word/pair of its sentence (the D25 naming rule, src.replay.baits_omission._names).

Inputs: results/raw (main run stage main/MAIN, A06 stage a06/OMIT, mode live), committed tables.
Outputs: data/derived/rubric/natural_tension_features.csv, natural_tension_discordant.csv.

  PYTHONPATH=. .venv/bin/python -m scripts.a07.natural_tension
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.analysis.primary import load_calls
from src.replay.baits_extraction import manifest, source_lines
from src.replay.baits_omission import _names, _record_markers
from src.replay.traces import load_trace
from src.runner.jobs import original_bob_message

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
RUBRIC = ROOT / "data" / "derived" / "rubric"
NATURAL = ROOT / "data" / "derived" / "items" / "natural_error_set.csv"
OMISSION_DIR = ROOT / "data" / "derived" / "omission_baits"
FEATURES = RUBRIC / "natural_tension_features.csv"
DISCORDANT = RUBRIC / "natural_tension_discordant.csv"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def log_features(raw_log: str, rid: str, sentence: str, task_id: str) -> dict:
    log = json.loads(raw_log)
    ns = _norm(sentence)
    args, res_ids, saved, sources = [], [], [], []
    for e in log:
        tool, a, r = e.get("tool"), e.get("arguments") or {}, e.get("result")
        if tool == "resolve_records":
            args += [_norm(x) for x in (a.get("records") or []) if isinstance(x, str)]
            if isinstance(r, dict):
                res_ids += [i.get("record_id") for i in (r.get("items") or []) if isinstance(i, dict)]
        elif tool == "save_final_answer":
            try:
                saved.append(json.loads(a.get("answer") or "[]"))
            except (TypeError, ValueError):
                saved.append([])
        elif tool == "read_source" and isinstance(r, dict):
            sources.append(r.get("content") or "")
    final = saved[-1] if saved else []
    lines = source_lines(task_id)
    ids = [i for i, _ in lines]
    valid = {x["id"] for x in manifest()[task_id]["reference_items"]}
    pos = ids.index(rid) if rid in ids else None
    inc = [k for k, i in enumerate(ids) if i in valid and i in final]
    return dict(
        sentence_in_resolve_args=any(x == ns or (len(x) > 20 and (x in ns or ns in x)) for x in args),
        id_in_resolve_result=rid in res_ids,
        id_in_any_saved_answer=any(rid in s for s in saved),
        id_in_final_answer=rid in final,
        n_resolve_calls=sum(e.get("tool") == "resolve_records" for e in log),
        sentence_in_read_source=any(sentence in s for s in sources),
        n_read_source=len(sources),
        source_index=pos, n_source_records=len(ids),
        rel_position=None if pos is None else round(pos / max(len(ids) - 1, 1), 3),
        first_or_last=None if pos is None else pos in (0, len(ids) - 1),
        between_included_valid=None if pos is None else bool(inc and min(inc) < pos < max(inc)),
        final_answer_size=len(final))


def named_by_bob(content: str, raw_log: str, rid: str, markers) -> bool:
    """Bob's visible text outside the raw log (round-1 framing) plus his saved-answer reasoning names the
    record (D25 naming rule). Planted items: False by construction (D25 skips named records)."""
    framing = content.replace(raw_log, " ") if raw_log in content else content
    saved = " ".join((e.get("arguments") or {}).get("reasoning") or "" for e in json.loads(raw_log)
                     if e.get("tool") == "save_final_answer")
    return bool(_names(framing + " " + saved, rid, markers))


def _mentions(calls: pd.DataFrame, item: str, variants, version: str, rid: str, markers) -> dict:
    out = {}
    for v in variants:
        sub = calls[(calls.item_id == item) & (calls.variant == v) & (calls.version == version)].sort_values("draw")
        out[f"{v}_y"] = ";".join("" if pd.isna(y) else str(int(y)) for y in sub.y)
        out[f"{v}_reject_names_record"] = ";".join(
            "-" if y != 1 else str(int(bool(_names(t, rid, markers)))) for y, t in zip(sub.y, sub.reasoning))
    return out


def natural_rows(main: pd.DataFrame) -> list[dict]:
    nat = pd.read_csv(NATURAL)
    dec = pd.read_csv(RUBRIC / "natural_error_decidability.csv").set_index("item_id")
    ov = pd.read_csv(RUBRIC / "lexical_overlap.csv")
    ov = ov[(ov.source == "natural_error") & (ov.record_role == "missing")].set_index(["item_id", "record_id"])
    rows = []
    for r in nat[nat.error_type.isin(["omission", "both"])].itertuples():
        ev = load_trace(r.trace)["results"][int(r.ep_index)]["agents"]["bob"]["extraction_eval"]
        content, raw = original_bob_message(r.trace, int(r.ep_index))
        lines = dict(source_lines(r.peer_task_id))
        for rid in ev["missing_references"]:
            base = dict(kind="natural", item_id=r.item_id, task_id=r.peer_task_id, error_type=r.error_type,
                        record_id=rid, decidable=dec.loc[r.item_id, "decidable"], n_missing_in_item=len(ev["missing_references"]))
            if rid not in lines:
                rows.append(base | dict(note="record ID not in the task source"))
                continue
            sent = lines[rid]
            k = (r.item_id, rid)
            base["overlap_n"] = ov.loc[k, "overlap_n"] if k in ov.index else None
            mk = _record_markers(r.peer_task_id, rid)
            rows.append(base | dict(sentence=sent, named_by_bob=named_by_bob(content, raw, rid, mk))
                        | log_features(raw, rid, sent, r.peer_task_id)
                        | _mentions(main, r.item_id, ("N1", "N4"), "correct", rid, _record_markers(r.peer_task_id, rid)))
    return rows


def planted_rows(a06: pd.DataFrame) -> list[dict]:
    rows = []
    for p in sorted(OMISSION_DIR.glob("rep*_alice.json")):
        b = json.loads(p.read_text())
        rid, sent = b["removed_id"], b["removed_sentence"]
        rows.append(dict(kind="planted", item_id=b["item_id"], task_id=b["task_id"], error_type="omission",
                         record_id=rid, decidable=None, n_missing_in_item=1, overlap_n=None, sentence=sent,
                         named_by_bob=named_by_bob(b["bob_r1_content"], b["omission_raw_log"], rid,
                                                   _record_markers(b["task_id"], rid)))
                    | log_features(b["omission_raw_log"], rid, sent, b["task_id"])
                    | _mentions(a06, b["item_id"], ("R1", "R4"), "omission", rid, _record_markers(b["task_id"], rid)))
    return rows


def discordant(main: pd.DataFrame) -> pd.DataFrame:
    nat = pd.read_csv(NATURAL).set_index("item_id")
    dec = pd.read_csv(RUBRIC / "natural_error_decidability.csv").set_index("item_id")
    j = {}
    for v in ("N1", "N4"):
        s = main[(main.variant == v) & (main.version == "correct")].set_index("item_id")
        j[v], j[f"{v}_reasoning"] = s.y, s.reasoning
    d = pd.DataFrame(j).join(nat[["task_type", "error_type", "peer_task_id"]]).join(dec[["decidable"]])
    d = d.reset_index().rename(columns={"index": "item_id"}).sort_values("item_id")
    d["pattern"] = d.apply(lambda r: f"N1={int(r.N1)} N4={int(r.N4)}", axis=1)
    return d


def main():
    main_calls = load_calls(RAW, "main", "MAIN", "live")
    a06 = load_calls(RAW, "a06", "OMIT", "live")
    d = discordant(main_calls)
    totals = {"N1_rejects": int(d.N1.sum()), "N4_rejects": int(d.N4.sum()), "n": len(d)}
    disc = d[d.N1 != d.N4].drop(columns=["N1_reasoning", "N4_reasoning"])
    disc.to_csv(DISCORDANT, index=False)
    f = pd.DataFrame(natural_rows(main_calls) + planted_rows(a06))
    f.to_csv(FEATURES, index=False)
    print("totals", totals)
    print(disc[["item_id", "task_type", "error_type", "decidable", "pattern"]].to_string(index=False))
    feats = ["named_by_bob", "sentence_in_resolve_args", "id_in_resolve_result", "id_in_any_saved_answer", "sentence_in_read_source",
             "first_or_last", "between_included_valid"]
    print(f.groupby("kind")[feats].agg(lambda s: f"{int(s.fillna(False).astype(bool).sum())}/{s.notna().sum()}").T)
    print(f.groupby("kind").rel_position.describe())
    return totals, disc, f


if __name__ == "__main__":
    main()
