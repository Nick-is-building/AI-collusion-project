"""Data behind the paper figures (plan section 15; A07 task 3); called by scripts/analysis/verify_all.py.

Every plotted number is written into verification.json under "figure_data" and the figure script
(scripts/analysis/figures.py) reads only that file. All values here are descriptive rates with 95% cluster
bootstrap intervals (plan 8.8: 10,000 resamples of trajectories, seed 2026; cell = mean of an item's draws).

  study0          Shi et al.'s 53 conditions: discrimination P(ACC|correct) - P(ACC|incorrect) with the
                  pre-sprint table's intervals (prior_work/1_reanalyse/trennschaerfe_alle_bedingungen.csv,
                  SHA-256 checked against devlog/01_foundation.md). Groups: "unconstrained" = the two
                  communication__*__unconstrained conditions (plan 2.3); every other condition is
                  "constrained or other" (context only).
  ladder          detection (bait / omission versions) and false rejection (correct versions) per variant,
                  commissions (main run, 109 items) and omissions (D25 items, 50).
  distance        the 40 R1-live items: detection R1, R5-post, R1-live; and false rejections R0 vs R0' (cut).
  countermeasure  operating points (false rejection, detection) for R1/R0', R4, R6, R6s, first and gated.
  study2          slot, filled when the Study 2 analysis is added (not by A07).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from scripts.analysis.a06_addendum import _ci, cluster_meta, load_stage, r1live_series
from scripts.analysis.a07_addendum import comparison_cells, load_a07
from src.analysis.primary import cell

ROOT = Path(__file__).resolve().parents[2]
STUDY0 = ROOT / "prior_work" / "1_reanalyse" / "trennschaerfe_alle_bedingungen.csv"
STUDY0_SHA256 = "e82c737b631ea66c198386c14092b4fe7e65882a239e2d1a7430134bab47609a"


def study0() -> dict:
    h = hashlib.sha256(STUDY0.read_bytes()).hexdigest()
    if h != STUDY0_SHA256:
        raise ValueError(f"{STUDY0} hash {h} != recorded {STUDY0_SHA256}")
    d = pd.read_csv(STUDY0)
    rows = []
    for r in d.itertuples():
        parts = r.Bedingung.split("__")
        unc = parts[0] == "communication" and parts[-1] == "unconstrained"
        rows.append(dict(condition=r.Bedingung, group="unconstrained" if unc else "constrained or other",
                         discrimination=float(r.Trennschaerfe), ci_low=float(r.KI_lo), ci_high=float(r.KI_hi),
                         p_accept_correct=float(r.P_acc_korrekt), p_accept_incorrect=float(r.P_acc_falsch),
                         n_incorrect=int(r.n_falsch)))
    s = pd.Series([r["discrimination"] for r in rows])
    return dict(source=str(STUDY0.relative_to(ROOT)), sha256=h, label="pre-sprint reanalysis (Study 0), reproduced in A01",
                n_conditions=len(rows), median=float(s.median()), max=float(s.max()), conditions=rows)


def _rate(series: pd.Series, meta) -> dict:
    """Mean of item cells with the cluster bootstrap CI of the mean."""
    return _ci(series.dropna(), meta)


def ladder(main: pd.DataFrame, a06: pd.DataFrame, a07: pd.DataFrame, comp: pd.DataFrame, meta) -> dict:
    com = {"detection": {}, "false_rejection": {}}
    for v in ("R1", "R2", "R3", "R4", "R4n", "R5"):
        com["detection"][v] = _rate(cell(main, v, "bait"), meta)
    com["detection"]["R6 first"] = _rate(cell(main, "R6", "bait", "r6_first_y"), meta)
    com["detection"]["R6 gated"] = _rate(cell(main, "R6", "bait", "r6_final_y"), meta)
    com["false_rejection"]["R1 (R0')"] = _rate(cell(main, "R0p", "correct"), meta)
    for v in ("R2", "R3", "R4", "R4n", "R5"):
        com["false_rejection"][v] = _rate(cell(main, v, "correct"), meta)
    com["false_rejection"]["R6 first"] = _rate(cell(main, "R6", "correct", "r6_first_y"), meta)
    com["false_rejection"]["R6 gated"] = _rate(cell(main, "R6", "correct", "r6_final_y"), meta)
    om = {"detection": {}, "false_rejection": {}}
    omit = a06[a06.check == "OMIT"]
    om["detection"]["R1"] = _rate(cell(omit, "R1", "omission"), meta)
    om["detection"]["R4"] = _rate(cell(omit, "R4", "omission"), meta)
    om["false_rejection"]["R1 (R0')"] = _rate(cell(comp, "R0p", "correct"), meta)
    items = set(cell(omit, "R1", "omission").index)
    r4c = pd.concat([main[main.item_id.isin(items) & (main.variant == "R4") & (main.version == "correct")],
                     omit[(omit.variant == "R4") & (omit.version == "correct")]])
    om["false_rejection"]["R4"] = _rate(cell(r4c, "R4", "correct"), meta)
    if len(a07):
        om["detection"]["R6 first"] = _rate(cell(a07, "R6", "omission", "r6_first_y"), meta)
        om["detection"]["R6 gated"] = _rate(cell(a07, "R6", "omission", "r6_final_y"), meta)
        om["detection"]["R6s first"] = _rate(cell(a07, "R6s", "omission", "r6s_first_y"), meta)
        om["detection"]["R6s gated"] = _rate(cell(a07, "R6s", "omission", "r6s_final_y"), meta)
        om["false_rejection"]["R6s first"] = _rate(cell(a07, "R6s", "correct", "r6s_first_y"), meta)
        om["false_rejection"]["R6s gated"] = _rate(cell(a07, "R6s", "correct", "r6s_final_y"), meta)
    return {"commission": com, "omission": om,
            "note": "omission R6 was run on omission versions only (D28); its false rejection is not measured "
                    "on these items"}


def distance(main: pd.DataFrame, a06: pd.DataFrame, meta) -> dict:
    from src.runner.item_lists import r1live_subset
    sub = r1live_subset()
    r1 = cell(main[main.item_id.isin(sub)], "R1", "bait")
    rp = a06[a06.check == "R5POST"]
    return {"n_items": len(sub),
            "detection": {"R1 (cut)": _rate(r1, meta), "R5-post": _rate(cell(rp, "R5post", "bait"), meta),
                          "R1-live": _rate(r1live_series(), meta)},
            "false_rejection_cut": {"R0 (no cut)": _rate(cell(main, "R0", "correct"), meta),
                                    "R0' (cut)": _rate(cell(main, "R0p", "correct"), meta)}}


def countermeasure(lad: dict) -> dict:
    """Operating points (x = false rejection, y = detection) assembled from the ladder cells."""
    c, o = lad["commission"], lad["omission"]
    pts = [("commission", "R1 / R0'", c["detection"]["R1"], c["false_rejection"]["R1 (R0')"]),
           ("commission", "R4", c["detection"]["R4"], c["false_rejection"]["R4"]),
           ("commission", "R6 first", c["detection"]["R6 first"], c["false_rejection"]["R6 first"]),
           ("commission", "R6 gated", c["detection"]["R6 gated"], c["false_rejection"]["R6 gated"]),
           ("omission", "R1 / R0'", o["detection"]["R1"], o["false_rejection"]["R1 (R0')"]),
           ("omission", "R4", o["detection"]["R4"], o["false_rejection"]["R4"])]
    for k in ("R6s first", "R6s gated"):
        if k in o["detection"]:
            pts.append(("omission", k, o["detection"][k], o["false_rejection"][k]))
    out = [dict(error=e, variant=v, detection=d, false_rejection=f) for e, v, d, f in pts]
    if "R6 first" in o["detection"]:
        for k in ("R6 first", "R6 gated"):
            out.append(dict(error="omission", variant=k, detection=o["detection"][k],
                            false_rejection=c["false_rejection"][k],
                            note="false rejection from the main-run commission items (R6 on correct versions); "
                                 "not measured on the omission items"))
    return {"points": out}


def build(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    meta = cluster_meta()
    a06 = load_stage("a06")
    a07 = load_a07()
    comp = comparison_cells(main_calls.assign(check="MAIN"), a06)
    lad = ladder(main_calls, a06, a07, comp, meta)
    return {"label": "DESCRIPTIVE figure data (rates with 95% cluster bootstrap CIs)", "study0": study0(),
            "ladder": lad, "distance": distance(main_calls, a06, meta), "countermeasure": countermeasure(lad),
            "study2": {"status": "slot; not filled by A07"}}
