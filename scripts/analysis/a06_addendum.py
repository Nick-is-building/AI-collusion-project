"""A06 addendum analyses (D25, D26) and exploratory readings; called by scripts/analysis/verify_all.py.
Written and committed before any D25/D26 call was made.

D25 omission baits (outside the Holm family, alpha 0.05):
  cells: R1 and R4 on the omission version (2 draws each, stage a06 check OMIT); correct counterparts
  R0' and R4-correct (2 draws each): from the main run for main-list items, from stage a06 otherwise.
  Delta_om = Detection(R4, omission) - Detection(R1, omission), paired per item; cluster sign-flip test
  and cluster bootstrap CI (plan 8.8; clusters = trajectories; 10,000, seed 2026).
  D_om as in plan 8.6 (gatekeeping: tested only if Delta_om is significant):
    D_i = [y(R4,om) - y(R4,correct)] - [y(R1,om) - y(R0',correct)].
  Missing verdicts excluded pairwise; sensitivity with missing as ACCEPT / REJECT.
  Descriptive: detection and false rejection; commission detection (main-run R1/R4 bait) on all 109 items
  and on the main-list items that also have an omission version; natural omissions (N1/N4, error type
  "omission"); deterministic right-reason share (removed record ID or sentence in the reasoning).
D26 R5-post (descriptive): detection R5-post (2 draws) vs R1 (main run, 2 draws) and R1-live (1 draw) on
  the 40 R1-live items; per-item differences with cluster bootstrap 95% CIs (no test).
Exploratory: right-reason by Claude Code reading (data/derived/rubric/right_reason_readings.csv) next to
  the deterministic markers, with the P11 deterministic share recomputed from the pilot raw files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.analysis.primary import ALPHA, _y, calls_frame, cell, paired, right_reason, test_contrast
from src.analysis.stats import cluster_bootstrap_ci
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
OMISSION_DIR = ROOT / "data" / "derived" / "omission_baits"
READINGS = ROOT / "data" / "derived" / "rubric" / "right_reason_readings.csv"


def load_stage(stage: str, raw: Path = RAW, mode: str = "live") -> pd.DataFrame:
    """Calls frame of one stage, with the `check` column (one line per call_id, the last one kept)."""
    seen = {}
    for r in iter_call_lines(raw):
        if r.get("stage") == stage and r.get("mode") == mode:
            seen[r["call_id"]] = r
    recs = list(seen.values())
    f = calls_frame(recs)
    if len(f):
        f["check"] = [r.get("check") for r in recs]
    return f


def r1live_series(raw: Path = RAW) -> pd.Series:
    live = [r for r in iter_call_lines(raw) if r.get("stage") == "r1live" and r.get("mode") == "live"]
    return pd.Series({r["item_id"]: _y(r.get("verdict"), r.get("verdict_status")) for r in live}, dtype=float).dropna()


def cluster_meta() -> pd.DataFrame:
    c = pd.read_csv(ROOT / "data" / "derived" / "items" / "candidates.csv")
    n = pd.read_csv(ROOT / "data" / "derived" / "items" / "natural_error_set.csv")
    m = pd.concat([c[["item_id", "trace"]], n[["item_id", "trace"]]]).drop_duplicates("item_id")
    return m.assign(cluster=m.trace.str.split(".").str[0]).set_index("item_id")


def _ci(d: pd.Series, meta) -> dict:
    if len(d) == 0:
        return dict(estimate=None, ci_low=None, ci_high=None, n_items=0)
    ci = cluster_bootstrap_ci(d.values, meta.loc[d.index, "cluster"].values)
    return dict(estimate=float(d.mean()), ci_low=ci["ci_low"], ci_high=ci["ci_high"], n_items=len(d),
                n_clusters=int(meta.loc[d.index, "cluster"].nunique()))


def _mean(s: pd.Series):
    return float(s.mean()) if len(s) else None


def d25(main_calls: pd.DataFrame, a06: pd.DataFrame, meta) -> dict:
    main_calls = main_calls.assign(check="MAIN")
    om = a06[a06.check == "OMIT"] if len(a06) else a06
    items = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))
    if om.empty:
        return {"status": "not run", "n_items_built": len(items)}
    correct = pd.concat([main_calls[main_calls.item_id.isin(items) & main_calls.variant.isin(["R0p", "R4"])
                                    & (main_calls.version == "correct")],
                         om[om.version == "correct"]])
    calls = pd.concat([om[om.version == "omission"], correct])
    out = {"n_items_built": len(items), "n_items_with_calls": int(om.item_id.nunique()),
           "correct_counterparts": {"from_main_run": int(correct[correct.check == "MAIN"].item_id.nunique()),
                                    "from_a06": int(correct[correct.check == "OMIT"].item_id.nunique())}}
    for miss in ("exclude", "accept", "reject"):
        r4, r1 = cell(calls, "R4", "omission", missing=miss), cell(calls, "R1", "omission", missing=miss)
        delta = test_contrast(paired(r4, r1), meta)
        r4c, r0p = cell(calls, "R4", "correct", missing=miss), cell(calls, "R0p", "correct", missing=miss)
        j = pd.concat([r4.rename("r4"), r4c.rename("r4c"), r1.rename("r1"), r0p.rename("r0p")], axis=1).dropna()
        dser = (j.r4 - j.r4c) - (j.r1 - j.r0p)
        sig = delta["p"] is not None and delta["p"] < ALPHA
        D = test_contrast(dser, meta) if sig else {"tested": False, "reason": "gatekeeping: Delta_om not significant",
                                                    "estimate_descriptive": _mean(dser)}
        res = {"Delta_om_R4_minus_R1": delta, "D_om": D, "detection_R1_om": _mean(r1), "detection_R4_om": _mean(r4),
               "false_rejection_R0p": _mean(r0p), "false_rejection_R4_correct": _mean(r4c)}
        if miss == "exclude":
            out.update(res)
            out["missing"] = int(calls.y.isna().sum())
        else:
            out[f"missing_as_{miss}"] = res
    # descriptive comparisons
    r1b, r4b = cell(main_calls, "R1", "bait"), cell(main_calls, "R4", "bait")
    both = [i for i in items if i in r1b.index]
    out["commission_detection"] = {
        "all_main_items": {"R1": _mean(r1b), "R4": _mean(r4b), "n": len(r1b)},
        "items_with_omission_version": {"R1_bait": _mean(r1b.loc[both]), "R4_bait": _mean(r4b.loc[both]),
                                        "R1_omission": _mean(cell(calls, "R1", "omission").reindex(both).dropna()),
                                        "R4_omission": _mean(cell(calls, "R4", "omission").reindex(both).dropna()),
                                        "n": len(both)}}
    nat = pd.read_csv(ROOT / "data" / "derived" / "items" / "natural_error_set.csv")
    nat_om = nat[nat.error_type == "omission"].item_id
    n1, n4 = cell(main_calls, "N1", "correct").reindex(nat_om).dropna(), cell(main_calls, "N4", "correct").reindex(nat_om).dropna()
    out["natural_omissions"] = {"N1": _mean(n1), "N4": _mean(n4), "n": len(n1)}
    rr = {}
    for v in ("R1", "R4"):
        sub = calls[(calls.variant == v) & (calls.version == "omission") & (calls.y == 1)]
        hits = [right_reason(t, json.loads((OMISSION_DIR / f"{i}.json").read_text())["right_reason_markers"])
                for t, i in zip(sub.reasoning, sub.item_id)]
        rr[v] = {"rejects": len(sub), "right_reason": int(sum(hits)), "share": _mean(pd.Series(hits, dtype=float))}
    out["right_reason_deterministic"] = rr
    return out


def d26(main_calls: pd.DataFrame, a06: pd.DataFrame, meta, rl: pd.Series) -> dict:
    from src.runner.item_lists import r1live_subset
    rp = a06[a06.check == "R5POST"] if len(a06) else a06
    if rp.empty:
        return {"status": "not run"}
    sub = r1live_subset()
    r5p = cell(rp, "R5post", "bait")
    r1 = cell(main_calls[main_calls.item_id.isin(sub)], "R1", "bait")
    return {"label": "descriptive (D26)", "n_items": int(r5p.size), "missing": int(rp.y.isna().sum()),
            "detection": {"R5post": _mean(r5p), "R1": _mean(r1), "R1live": _mean(rl)},
            "R5post_minus_R1": _ci(paired(r5p, r1), meta), "R5post_minus_R1live": _ci(paired(r5p, rl), meta),
            "R1live_minus_R1": _ci(paired(rl, r1), meta)}


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    a06 = load_stage("a06")
    meta = cluster_meta()
    return {"label": "ADDENDUM (D25, D26; fixed before any outcome analysis; outside the Holm family)",
            "D25_omission": d25(main_calls, a06, meta), "D26_R5post": d26(main_calls, a06, meta, r1live_series()),
            "spend_usd_a06": float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                       if r.get("stage") == "a06" and r.get("mode") == "live"))}


def p11_deterministic_share() -> dict:
    """Recomputed from the pilot raw files: P11 bait REJECTs (hold-out items) with a deterministic marker,
    under three marker sets: the bait files' plan markers only (the "22 of 32" in A06), the preregistered
    analysis markers (src.analysis.meta._markers: plus the added categorical value), and the R1-live (a)
    markers (plus the relaxed literal, D19 addendum)."""
    from src.analysis.meta import _markers
    from src.replay.r1live_screen import markers as live_markers, norm
    from src.runner.item_lists import load_bait
    recs = [r for r in iter_call_lines(RAW) if r.get("stage") == "pilot" and r.get("check") == "P11"
            and r.get("mode") == "live" and r.get("verdict") == "reject"]
    plan = analysis = live = 0
    for r in recs:
        b, t = load_bait(r["item_id"]), r.get("reasoning") or ""
        plan += right_reason(t, b.get("right_reason_markers") or {})
        analysis += right_reason(t, _markers(b))
        live += any(m in norm(t) for m in live_markers(b))
    return {"bait_rejects": len(recs), "plan_markers_only": int(plan), "prereg_analysis_markers": int(analysis),
            "r1live_markers": int(live)}


def exploratory(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    out = {"right_reason_reading": {"label": "EXPLORATORY", "p11_disclosure": p11_deterministic_share()}}
    if not READINGS.exists():
        out["right_reason_reading"]["status"] = "readings not done"
        return out
    rd = pd.read_csv(READINGS)
    rows = []
    for (scope, v), g in rd.groupby(["scope", "variant"]):
        rows.append(dict(scope=scope, variant=v, n=len(g), deterministic=int(g.deterministic.sum()),
                         reading_yes=int((g.reading == "yes").sum()), reading_no=int((g.reading == "no").sum()),
                         reading_unclear=int((g.reading == "unclear").sum()),
                         agree=int(((g.reading == "yes") == g.deterministic.astype(bool)).sum())))
    out["right_reason_reading"]["table"] = rows
    out["right_reason_reading"]["source"] = "Claude Code reading of the reasoning text (A06); see the readings file"
    return out
