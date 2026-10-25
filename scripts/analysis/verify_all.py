"""The one verification script for every Study 1 number (plan 23.4; assignment A06).

Reads only the raw JSONL call lines in results/raw plus committed tables, and writes
results/summaries/verification.json. Sections are kept apart by status:

  confirmatory  prereg-v1 (frozen code, scripts/analysis/run_study1.py: primary, gatekeeping, secondary
                Holm family, cut-artifact, sensitivities, descriptive, N1/N4 by error type, fidelity) and
                prereg-v1-r1live (frozen src/analysis/r1live.py, with the confirming readings in
                data/derived/rubric/r1live_readings.csv).
                Natural errors by decidability (D24) are descriptive, as the natural-error set is (plan 8.8).
  addendum      D25 omission baits and D26 R5-post (fixed before any outcome was analysed; outside Holm).
                D28 R6s source enumeration (A07; fixed before its own run; outside Holm), key "D28_R6s".
                D30 R6x exhaustive source classification and D31 R6 on the correct versions of the omission
                items (A08; fixed before their own run; outside Holm), key "D30_D31_R6x".
                Reported as "not run" until their call lines exist.
  exploratory   equivalence reading (margin +-0.10) of the preregistered contrasts; right-reason detection
                by Claude Code reading next to the deterministic markers. Labelled exploratory.

  .venv/bin/python -m scripts.analysis.verify_all
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analysis import run_study1
from src.analysis.meta import main_meta, natural_meta
from src.analysis.primary import EQUIV_MARGIN, cell, load_calls, to_json
from src.analysis.r1live import analyze_r1live, live_frame
from src.runner.costs import iter_call_lines
from src.runner.item_lists import load_bait, r1live_subset

ROOT = Path(__file__).resolve().parents[2]
RUBRIC = ROOT / "data" / "derived" / "rubric"
SUMMARIES = ROOT / "results" / "summaries"


# ---------------------------------------------------------------- confirmatory

def natural_by_decidability(calls: pd.DataFrame) -> dict:
    """N1 and N4 detection (REJECT share, single draw) by D24 class and by error type x class."""
    cl = pd.read_csv(RUBRIC / "natural_error_decidability.csv").set_index("item_id")
    n1, n4 = cell(calls, "N1", "correct"), cell(calls, "N4", "correct")
    j = pd.concat([n1.rename("N1"), n4.rename("N4")], axis=1).join(cl[["error_type", "decidable"]], how="inner")

    def agg(g):
        return dict(items=len(g), detection_N1=float(g.N1.mean()), detection_N4=float(g.N4.mean()),
                    N4_minus_N1=float((g.N4 - g.N1).mean()), N1_rejects=int(g.N1.sum()), N4_rejects=int(g.N4.sum()))
    return dict(
        note="descriptive (plan 8.8); classes by Claude Code reading (D24, docs/natural_error_rubric.md)",
        by_decidability={k: agg(g) for k, g in j.groupby("decidable")},
        by_error_type_and_decidability=[dict(error_type=e, decidable=d, **agg(g))
                                        for (e, d), g in j.groupby(["error_type", "decidable"])],
        overall=agg(j))


def r1live_section(main_calls: pd.DataFrame, meta: pd.DataFrame) -> dict:
    recs = [r for r in iter_call_lines(ROOT / "results" / "raw") if r.get("stage") == "r1live" and r.get("mode") == "live"]
    subset = r1live_subset()
    baits = {i: load_bait(i) for i in subset}
    live = live_frame(recs, baits)
    rd = pd.read_csv(RUBRIC / "r1live_readings.csv").set_index("item_id")
    flag_b = set(rd.index[rd.flag_b_confirmed.astype(bool)])
    reaction = {i: r for i, r in rd.bob_reaction_confirmed.dropna().items()}
    cand = pd.read_csv(ROOT / "data" / "derived" / "items" / "candidates.csv")
    out = analyze_r1live(main_calls, live, meta, subset, cand, flag_b, reaction)
    out["readings"] = "confirming readings by Claude Code (D19.8): data/derived/rubric/r1live_readings.csv"
    out["n_live_calls"] = len(recs)
    return out


# ---------------------------------------------------------------- exploratory

def equivalence_reading(conf: dict) -> dict:
    """Exploratory: is each preregistered contrast's 95% cluster bootstrap CI inside [-0.10, +0.10]?"""
    s1 = conf["prereg_v1"]
    items = {"Delta_R4_minus_R1": s1["primary"]["Delta_R4_minus_R1"], "cut_artifact_R0p_minus_R0": s1["cut_artifact"]}
    if "ci_low" in s1["primary"]["D"]:
        items["D"] = s1["primary"]["D"]
    items.update({f"secondary_{k}": v for k, v in s1["secondary"].items()})
    items["R1live_minus_R1"] = conf["prereg_v1_r1live"]["primary"]
    out = {}
    for k, t in items.items():
        lo, hi = t.get("ci_low"), t.get("ci_high")
        out[k] = dict(estimate=t.get("estimate"), ci_low=lo, ci_high=hi,
                      inside_margin=None if lo is None else bool(lo >= -EQUIV_MARGIN and hi <= EQUIV_MARGIN))
    return dict(label="EXPLORATORY", margin=EQUIV_MARGIN, contrasts=out,
                caveat="near-ceiling cells give degenerate intervals (e.g. [0, 0]); inside the margin is not "
                       "evidence of equivalence of the underlying abilities, only of the observed rates")


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SUMMARIES / "verification.json"))
    a = ap.parse_args(argv)
    meta = main_meta()
    calls = load_calls(ROOT / "results" / "raw", "main", "MAIN", "live")
    s1 = run_study1.main(["--out", str(SUMMARIES / "study1_analysis.json")])   # frozen prereg-v1 analysis
    conf = {"prereg_v1": s1, "natural_by_decidability": natural_by_decidability(calls),
            "prereg_v1_r1live": r1live_section(calls, meta)}
    res = {"confirmatory": conf, "addendum": {}, "exploratory": {"equivalence": equivalence_reading(conf)}}
    if (ROOT / "scripts" / "analysis" / "a06_addendum.py").exists():
        from scripts.analysis import a06_addendum
        res["addendum"] = a06_addendum.analyze(calls, meta)
        res["exploratory"].update(a06_addendum.exploratory(calls, meta))
    else:
        res["addendum"] = {"status": "not run"}
    if (ROOT / "scripts" / "analysis" / "a07_addendum.py").exists():   # A07: D28 R6s (A07 calls it D27)
        from scripts.analysis import a07_addendum
        res["addendum"]["D28_R6s"] = a07_addendum.analyze(calls, meta)
    if (ROOT / "scripts" / "analysis" / "a08_addendum.py").exists():   # A08: D30 R6x and D31 R6 correct versions
        from scripts.analysis import a08_addendum
        res["addendum"]["D30_D31_R6x"] = a08_addendum.analyze(calls, meta)
    if (ROOT / "scripts" / "analysis" / "a10_addendum.py").exists():   # A10: D32-D34 incentive and peer-signal arms
        from scripts.analysis import a10_addendum
        res["addendum"]["a10"] = a10_addendum.analyze(calls, meta)
    from scripts.analysis import figure_data   # A07 task 3: data behind paper/figures (descriptive)
    res["figure_data"] = figure_data.build(calls, meta)
    Path(a.out).write_text(to_json(res))
    print("wrote", a.out)
    return res


if __name__ == "__main__":
    main()
