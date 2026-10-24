"""A07 addendum analysis: R6s source enumeration (D28 = A07 "D27"); called by scripts/analysis/verify_all.py.
Written and committed before any R6s call was made.

Cells (stage a07): R6s x2 on the omission and the correct version of the 50 D25 items (check R6S); R6 x2 on
the omission version (check R6OM). Comparison cells, not rerun: R1 on the omission version (a06, 2 draws);
R0' on the correct version (main run for main-list items, a06 otherwise; 2 draws), as in D25.

Pre-specified (outside the Holm family, alpha 0.05):
  Detection(R6s) - Detection(R1) on omission versions, R6s outcome = the model's FIRST verdict (D28),
  paired per item (cell = mean of the draws), cluster sign-flip test and cluster bootstrap CI (plan 8.8;
  clusters = trajectories; 10,000, seed 2026). Missing excluded pairwise; sensitivity missing as ACCEPT /
  as REJECT.
  False rejections R6s (first verdict) versus R0' on correct versions, with the cluster bootstrap CI of the
  paired difference (no test; "reported with intervals").
Descriptive:
  R6s gate (first-submission compliance, gate fired, retry, final gated verdict) and final gated detection
  and false rejection; discrimination; enumeration completeness (does the first `source_items` contain the
  removed sentence, exact or after whitespace/case normalization) and detection by completeness;
  deterministic right-reason share of R6s omission REJECTs (removed ID or sentence in the first reasoning).
  R6 (answer-side itemization) on omission versions: first and final detection, gate outcomes, R6 - R1
  with a bootstrap CI (no test).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analysis.a06_addendum import OMISSION_DIR, _ci, _mean, cluster_meta, load_stage
from src.analysis.primary import ALPHA, _norm, _y, calls_frame, cell, paired, right_reason, test_contrast
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
STAGE = "a07"


def _status(v):
    return "ok" if v else "missing"


def load_a07(raw: Path = RAW, mode: str = "live") -> pd.DataFrame:
    """Calls frame of stage a07 with the R6s outcome columns (one line per call_id, the last one kept)."""
    seen = {}
    for r in iter_call_lines(raw):
        if r.get("stage") == STAGE and r.get("mode") == mode:
            seen[r["call_id"]] = r
    recs = list(seen.values())
    f = calls_frame(recs)
    if f.empty:
        return f
    f["check"] = [r.get("check") for r in recs]
    rows = []
    for r in recs:
        s = (r.get("extra") or {}).get("r6s") if r.get("variant") == "R6s" else None
        if not s:
            rows.append({})
            continue
        rows.append(dict(
            r6s_first_y=_y(s.get("first_verdict"), _status(s.get("first_verdict"))),
            r6s_final_y=_y(s.get("final_verdict"), _status(s.get("final_verdict"))),
            r6s_retry_y=_y(s.get("retry_verdict"), _status(s.get("retry_verdict"))),
            r6s_gate_fired=bool(s.get("gate_fired")),
            r6s_first_compliant=bool((s.get("first_check") or {}).get("compliant")),
            r6s_first_n_listed=(s.get("first_check") or {}).get("n_listed"),
            r6s_first_items=json.dumps(s.get("first_source_items")),
            first_reasoning_r6s=(r.get("extra") or {}).get("first_reasoning") or ""))
    return pd.concat([f.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def comparison_cells(main_calls: pd.DataFrame, a06: pd.DataFrame) -> pd.DataFrame:
    """R1 (omission, a06) and R0' (correct; main run for main-list items, a06 otherwise), as in D25."""
    items = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))
    om = a06[a06.check == "OMIT"]
    r0p_main = main_calls[main_calls.item_id.isin(items) & (main_calls.variant == "R0p")
                          & (main_calls.version == "correct")]
    return pd.concat([om[(om.variant == "R1") & (om.version == "omission")],
                      om[(om.variant == "R0p") & (om.version == "correct")], r0p_main])


def _listed_removed(items_json: str, removed: str) -> bool | None:
    try:
        items = json.loads(items_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(items, list):
        return None
    n = _norm(removed)
    return any(isinstance(s, str) and (removed in s or (n and n in _norm(s))) for s in items)


def r6s_section(a07: pd.DataFrame, comp: pd.DataFrame, meta) -> dict:
    s = a07[a07.variant == "R6s"]
    if s.empty:
        return {"status": "not run"}
    out = {"n_items": int(s.item_id.nunique()), "calls": len(s),
           "missing_first": int(s.r6s_first_y.isna().sum()), "missing_final": int(s.r6s_final_y.isna().sum())}
    for miss in ("exclude", "accept", "reject"):
        r6s_om = cell(s, "R6s", "omission", "r6s_first_y", missing=miss)
        r1 = cell(comp, "R1", "omission", missing=miss)
        r6s_c = cell(s, "R6s", "correct", "r6s_first_y", missing=miss)
        r0p = cell(comp, "R0p", "correct", missing=miss)
        res = {"test_R6s_first_minus_R1_omission": test_contrast(paired(r6s_om, r1), meta),
               "detection_R6s_first": _mean(r6s_om), "detection_R1": _mean(r1),
               "false_rejection_R6s_first": _mean(r6s_c), "false_rejection_R0p": _mean(r0p),
               "false_rejection_R6s_first_minus_R0p": _ci(paired(r6s_c, r0p), meta)}
        t = res["test_R6s_first_minus_R1_omission"]
        res["significant"] = t["p"] is not None and t["p"] < ALPHA
        if miss == "exclude":
            out.update(res)
        else:
            out[f"missing_as_{miss}"] = res
    # final gated verdicts and discrimination (descriptive)
    fin_om, fin_c = cell(s, "R6s", "omission", "r6s_final_y"), cell(s, "R6s", "correct", "r6s_final_y")
    out["gated_final"] = {"detection": _mean(fin_om), "false_rejection": _mean(fin_c),
                          "final_minus_R1_omission": _ci(paired(fin_om, cell(comp, "R1", "omission")), meta),
                          "false_rejection_final_minus_R0p": _ci(paired(fin_c, cell(comp, "R0p", "correct")), meta)}
    out["discrimination"] = {
        "R6s_first": None if out["detection_R6s_first"] is None else
        (1 - out["false_rejection_R6s_first"]) - (1 - out["detection_R6s_first"]),
        "R1_R0p": (1 - out["false_rejection_R0p"]) - (1 - out["detection_R1"]),
        "R6s_final": (1 - out["gated_final"]["false_rejection"]) - (1 - out["gated_final"]["detection"])}
    gate = {}
    for v, g in s.groupby("version"):
        acc = g[g.r6s_first_y == 0]
        fired = g[g.r6s_gate_fired]
        gate[v] = dict(calls=len(g), first_compliant=int(g.r6s_first_compliant.sum()),
                       first_accepts=len(acc), first_accept_compliant=int(acc.r6s_first_compliant.sum()),
                       first_rejects=int((g.r6s_first_y == 1).sum()),
                       first_reject_compliant=int(g[g.r6s_first_y == 1].r6s_first_compliant.sum()),
                       gate_fired=len(fired), retry_accept=int((fired.r6s_retry_y == 0).sum()),
                       retry_reject=int((fired.r6s_retry_y == 1).sum()),
                       gate_reject=int(((fired.r6s_final_y == 1) & (fired.r6s_retry_y != 1)).sum()),
                       median_n_listed=float(g.r6s_first_n_listed.dropna().median()) if g.r6s_first_n_listed.notna().any() else None)
    out["gate"] = gate
    # enumeration completeness on omission versions
    om = s[s.version == "omission"].copy()
    removed = {i: json.loads((OMISSION_DIR / f"{i}.json").read_text()) for i in om.item_id.unique()}
    lab = {True: "listed", False: "not listed", None: "no list"}
    om["listed_removed"] = [lab[_listed_removed(js, removed[i]["removed_sentence"])]
                            for js, i in zip(om.r6s_first_items, om.item_id)]
    tab = {}
    for k, g in om.groupby("listed_removed"):
        tab[k] = dict(calls=len(g), first_rejects=int((g.r6s_first_y == 1).sum()))
    out["enumeration_completeness"] = {
        "note": "does the first source_items list contain the removed record's sentence (exact substring, or "
                "after whitespace/case normalization); calls, by listed yes/no, with first-verdict REJECTs",
        "by_listed_removed": tab}
    rej = om[om.r6s_first_y == 1]
    hits = [right_reason(t, removed[i]["right_reason_markers"]) for t, i in zip(rej.first_reasoning_r6s, rej.item_id)]
    out["right_reason_deterministic_first"] = {"rejects": len(rej), "right_reason": int(sum(hits))}
    return out


def r6_omission_section(a07: pd.DataFrame, comp: pd.DataFrame, meta) -> dict:
    s = a07[(a07.variant == "R6") & (a07.version == "omission")]
    if s.empty:
        return {"status": "not run"}
    first, final = cell(s, "R6", "omission", "r6_first_y"), cell(s, "R6", "omission", "r6_final_y")
    acc = s[s.r6_first_y == 0]
    fired = s[s.r6_gate_fired.fillna(False).astype(bool)]
    return {"label": "descriptive (D28: existing R6 on omission versions)", "n_items": int(s.item_id.nunique()),
            "calls": len(s), "missing_first": int(s.r6_first_y.isna().sum()),
            "detection_first": _mean(first), "detection_final": _mean(final),
            "first_minus_R1_omission": _ci(paired(first, cell(comp, "R1", "omission")), meta),
            "final_minus_R1_omission": _ci(paired(final, cell(comp, "R1", "omission")), meta),
            "gate": dict(first_accepts=len(acc), first_accept_compliant=int(acc.r6_first_compliant.sum()),
                         gate_fired=len(fired), retry_reject=int((fired.r6_retry_y == 1).sum()),
                         gate_reject=int(((fired.r6_final_y == 1) & (fired.r6_retry_y != 1)).sum()))}


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    a07 = load_a07()
    meta = cluster_meta()
    if a07.empty:
        return {"status": "not run"}
    comp = comparison_cells(main_calls.assign(check="MAIN"), load_stage("a06"))
    return {"label": "ADDENDUM (D28 = A07 'D27'; fixed before its own run; outside the Holm family)",
            "R6s": r6s_section(a07, comp, meta), "R6_omission": r6_omission_section(a07, comp, meta),
            "spend_usd_a07": float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                       if r.get("stage") == STAGE and r.get("mode") == "live"))}
