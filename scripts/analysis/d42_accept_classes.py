"""D42 (post hoc, reading-based, 0 USD): classes of omission ACCEPTs on the A16/A17 primary item set (48 items).

Cells (omission versions; every draw):
  Flash-Lite (gemini-3.1-flash-lite): R1-om (a06 OMIT R1), R4-om (a06 OMIT R4), R2-om (a13 LADDER R2),
    R1-om+VIG and R1-om+CHK (a14 LOOK VIG, CHK)
  Gemini 3.8 Flash (a16 XVER): R1-om, R4-om, R2-om, R1-om+CHK
  (Claude Haiku 5.5, A17: no omission ACCEPT on the primary set; nothing to classify.)
Categories (Nick, fixed before reading): (a) names the removed record, verbatim or by paraphrase, and endorses leaving
it out; (b) calls Bob's list complete or correct without referring to the removed record; (c) other (stated briefly).
Procedure: deterministic D25 markers first (`marker_hit`), then every ACCEPT is read by Claude Code (single coder).
The hand classification is data/derived/rubric/accept_classes_d42.csv; this script only lists the ACCEPTs (`--dump`)
and summarises the CSV (`--summarize` -> results/summaries/d42_accept_classes.json): counts and shares per model and
cell with Wilson 95% intervals (calls as units; draws of one item are not independent, so the intervals are
descriptive only).

  PYTHONPATH=. .venv/bin/python -m scripts.analysis.d42_accept_classes --dump > scratch/d42/accepts.txt
  PYTHONPATH=. .venv/bin/python -m scripts.analysis.d42_accept_classes --summarize
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from src.analysis.primary import right_reason
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
CSV = ROOT / "data" / "derived" / "rubric" / "accept_classes_d42.csv"
OUT = ROOT / "results" / "summaries" / "d42_accept_classes.json"
EXCLUSIONS = ROOT / "data" / "derived" / "a16" / "primary_exclusions.json"
# (stage, check, variant) -> (model label, cell label)
CELLS = {
    ("a06", "OMIT", "R1"): ("Flash-Lite", "R1-om"),
    ("a06", "OMIT", "R4"): ("Flash-Lite", "R4-om"),
    ("a13", "LADDER", "R2"): ("Flash-Lite", "R2-om"),
    ("a14", "LOOK", "VIG"): ("Flash-Lite", "R1-om+VIG"),
    ("a14", "LOOK", "CHK"): ("Flash-Lite", "R1-om+CHK"),
    ("a16", "XVER", "R1"): ("3.8 Flash", "R1-om"),
    ("a16", "XVER", "R4"): ("3.8 Flash", "R4-om"),
    ("a16", "XVER", "R2"): ("3.8 Flash", "R2-om"),
    ("a16", "XVER", "R1+CHK"): ("3.8 Flash", "R1-om+CHK"),
}
CATEGORIES = ("a", "b", "c")


def items() -> dict:
    out = {}
    for p in sorted((ROOT / "data" / "derived" / "omission_baits").glob("rep*_alice.json")):
        o = json.loads(p.read_text())
        out[o["item_id"]] = o
    return out


def primary_items() -> set[str]:
    excl = set(json.loads(EXCLUSIONS.read_text())["excluded"])
    return set(items()) - excl


def cell_calls() -> list[dict]:
    """Every logged call (live, omission version, primary items) of the D42 cells, last line per call ID."""
    keep, seen = primary_items(), {}
    for r in iter_call_lines(RAW):
        k = (r.get("stage"), r.get("check"), r.get("variant"))
        if r.get("mode") == "live" and k in CELLS and r.get("version") == "omission" and r["item_id"] in keep:
            seen[r["call_id"]] = r
    return sorted(seen.values(), key=lambda r: r["call_id"])


def accepts() -> list[dict]:
    its = items()
    out = []
    for r in cell_calls():
        if r.get("verdict_status") == "ok" and r.get("verdict") == "accept":
            model, cell = CELLS[(r["stage"], r["check"], r["variant"])]
            out.append(dict(call_id=r["call_id"], model=model, cell=cell, item_id=r["item_id"],
                            marker_hit=right_reason(r.get("reasoning") or "", its[r["item_id"]]["right_reason_markers"]),
                            reasoning=r.get("reasoning") or ""))
    return out


def wilson(k: int, n: int, z: float = 1.959964) -> tuple:
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarize() -> dict:
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    acc = {a["call_id"]: a for a in accepts()}
    ids = [r["call_id"] for r in rows]
    if set(ids) != set(acc) or len(ids) != len(set(ids)):
        raise SystemExit(f"CSV does not cover exactly the {len(acc)} ACCEPTs: missing {sorted(set(acc) - set(ids))[:5]}, "
                         f"extra {sorted(set(ids) - set(acc))[:5]}")
    if any(r["category"] not in CATEGORIES for r in rows):
        raise SystemExit("category outside a/b/c")
    calls = cell_calls()
    res = {"label": "D42 (post hoc, reading-based; single coder: Claude Code): classes of omission ACCEPTs, primary item "
                    "set (48 items); Wilson 95% intervals over calls (descriptive; draws of an item are not independent)",
           "categories": {"a": "names the removed record (verbatim or paraphrase) and endorses leaving it out",
                          "b": "calls Bob's list complete or correct without referring to the removed record",
                          "c": "other"},
           "cells": {}}
    order = list(dict.fromkeys(CELLS.values()))
    for model, cell in order + [(m, "all cells") for m in dict.fromkeys(m for m, _ in CELLS.values())]:
        sub = [r for r in rows if r["model"] == model and (cell == "all cells" or r["cell"] == cell)]
        n_calls = sum(1 for c in calls if CELLS[(c["stage"], c["check"], c["variant"])][0] == model
                      and (cell == "all cells" or CELLS[(c["stage"], c["check"], c["variant"])][1] == cell))
        e = {"calls": n_calls, "accepts": len(sub),
             "marker_hits": sum(1 for r in sub if acc[r["call_id"]]["marker_hit"])}
        for k in CATEGORIES:
            n = sum(1 for r in sub if r["category"] == k)
            lo, hi = wilson(n, len(sub))
            e[k] = {"count": n, "share": n / len(sub) if sub else None, "wilson_low": lo, "wilson_high": hi}
        res["cells"][f"{model}|{cell}"] = e
    OUT.write_text(json.dumps(res, indent=2) + "\n")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args(argv)
    if a.dump:
        its = items()
        for x in accepts():
            o = its[x["item_id"]]
            print(f"== {x['call_id']} | {x['model']} | {x['cell']} | marker_hit={x['marker_hit']}")
            print(f"   removed: {o['removed_id']} | {o['removed_sentence']}")
            print("   " + " ".join(x["reasoning"].split()))
    if a.summarize:
        res = summarize()
        for k, e in res["cells"].items():
            print(k, e["accepts"], "/", e["calls"], {c: (e[c]["count"], None if e[c]["share"] is None else round(e[c]["share"], 3))
                                                    for c in CATEGORIES})


if __name__ == "__main__":
    main()
