"""A08 addendum analysis: R6x exhaustive source classification (D30) and R6 on the correct versions of the
omission items (D31); called by scripts/analysis/verify_all.py. Written and committed before any A08 call.

Cells (stage a08): R6x x2 on the omission and the correct version of the 50 D25 items (check R6X); R6 x2 on
the correct version (check R6COR). Comparison cells, not rerun: R1 on the omission version (a06, 2 draws) and
R0' on the correct version (main run for main-list items, a06 otherwise; 2 draws), as in D25 and D28
(`scripts.analysis.a07_addendum.comparison_cells`).

D30 pre-specified test (outside the Holm family, alpha 0.05):
  Detection(R6x) - Detection(R1) on omission versions, R6x outcome = the model's FIRST verdict, paired per
  item (cell = mean of the draws), cluster sign-flip test and cluster bootstrap CI (plan 8.8; clusters =
  trajectories; 10,000, seed 2026). Missing excluded pairwise; sensitivity missing as ACCEPT / as REJECT.
D30 secondary, pre-specified (estimates with cluster bootstrap CIs, no test):
  - final gated verdict: detection and false rejection, and their paired differences to R1 / R0';
  - false rejections R6x (first verdict) against R0', paired difference with CI;
  - compliance rate of the first submission (gate rule, src.replay.r6x.check), by version, with the
    failure types (missing / duplicated / extra entries / bad labels) and the rate ignoring extra entries;
  - detection conditional on the missing sentence being labeled include: first-verdict REJECT share among
    omission calls whose first submission labels the removed sentence include (call level; counts of calls,
    items, trajectories). The other label groups (exclude, not listed, conflicting) are reported next to it.
Descriptive: gate counts; discrimination; deterministic right-reason share of first REJECTs on omissions.
D31 (descriptive): R6 false rejection on the correct versions of the 50 omission items, first and gated,
  with CIs and the paired difference to R0'; gate counts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analysis.a06_addendum import OMISSION_DIR, _ci, _mean, cluster_meta, load_stage
from scripts.analysis.a07_addendum import comparison_cells
from src.analysis.primary import ALPHA, _y, calls_frame, cell, paired, right_reason, test_contrast
from src.replay.r6x import label_of
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
STAGE = "a08"


def _status(v):
    return "ok" if v else "missing"


def load_a08(raw: Path = RAW, mode: str = "live") -> pd.DataFrame:
    """Calls frame of stage a08 with the R6x outcome columns (one line per call_id, the last one kept).
    R6 rows get calls_frame's r6_* columns."""
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
        s = (r.get("extra") or {}).get("r6x") if r.get("variant") == "R6x" else None
        if not s:
            rows.append({})
            continue
        c = s.get("first_check") or {}
        rows.append(dict(
            r6x_first_y=_y(s.get("first_verdict"), _status(s.get("first_verdict"))),
            r6x_final_y=_y(s.get("final_verdict"), _status(s.get("final_verdict"))),
            r6x_retry_y=_y(s.get("retry_verdict"), _status(s.get("retry_verdict"))),
            r6x_gate_fired=bool(s.get("gate_fired")),
            r6x_first_compliant=bool(c.get("compliant")),
            r6x_first_compliant_ignoring_extra=bool(c.get("compliant_ignoring_extra")),
            r6x_first_present=bool(c.get("present")),
            r6x_first_n_listed=c.get("n_listed"), r6x_first_n_source=c.get("n_source"),
            r6x_first_n_missing=len(c.get("missing") or []), r6x_first_n_duplicated=len(c.get("duplicated") or []),
            r6x_first_n_extra=c.get("n_extra"), r6x_first_n_bad_labels=len(c.get("bad_labels") or []),
            r6x_first_classification=json.dumps(s.get("first_classification")),
            first_reasoning_r6x=(r.get("extra") or {}).get("first_reasoning") or ""))
    return pd.concat([f.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def _compliance(g: pd.DataFrame) -> dict:
    n = len(g)
    return dict(calls=n, first_compliant=int(g.r6x_first_compliant.sum()),
                first_compliance_rate=float(g.r6x_first_compliant.mean()) if n else None,
                first_compliant_ignoring_extra=int(g.r6x_first_compliant_ignoring_extra.sum()),
                field_absent=int((~g.r6x_first_present.astype(bool)).sum()),
                with_missing=int((g.r6x_first_n_missing > 0).sum()),
                with_duplicated=int((g.r6x_first_n_duplicated > 0).sum()),
                with_extra=int((g.r6x_first_n_extra.fillna(0) > 0).sum()),
                with_bad_labels=int((g.r6x_first_n_bad_labels > 0).sum()),
                median_n_listed=float(g.r6x_first_n_listed.dropna().median()) if g.r6x_first_n_listed.notna().any() else None,
                median_n_source=float(g.r6x_first_n_source.dropna().median()) if g.r6x_first_n_source.notna().any() else None)


def r6x_section(a08: pd.DataFrame, comp: pd.DataFrame, meta) -> dict:
    s = a08[a08.variant == "R6x"]
    if s.empty:
        return {"status": "not run"}
    out = {"n_items": int(s.item_id.nunique()), "calls": len(s),
           "missing_first": int(s.r6x_first_y.isna().sum()), "missing_final": int(s.r6x_final_y.isna().sum())}
    # pre-specified test (primary: first verdict), with missing-verdict sensitivities
    for miss in ("exclude", "accept", "reject"):
        x_om = cell(s, "R6x", "omission", "r6x_first_y", missing=miss)
        r1 = cell(comp, "R1", "omission", missing=miss)
        x_c = cell(s, "R6x", "correct", "r6x_first_y", missing=miss)
        r0p = cell(comp, "R0p", "correct", missing=miss)
        res = {"test_R6x_first_minus_R1_omission": test_contrast(paired(x_om, r1), meta),
               "detection_R6x_first": _ci(x_om, meta), "detection_R1": _ci(r1, meta),
               "false_rejection_R6x_first": _ci(x_c, meta), "false_rejection_R0p": _ci(r0p, meta),
               "false_rejection_R6x_first_minus_R0p": _ci(paired(x_c, r0p), meta)}
        t = res["test_R6x_first_minus_R1_omission"]
        res["significant"] = t["p"] is not None and t["p"] < ALPHA
        if miss == "exclude":
            out.update(res)
        else:
            out[f"missing_as_{miss}"] = res
    # secondary: final gated verdict
    fin_om, fin_c = cell(s, "R6x", "omission", "r6x_final_y"), cell(s, "R6x", "correct", "r6x_final_y")
    out["gated_final"] = {
        "detection": _ci(fin_om, meta), "false_rejection": _ci(fin_c, meta),
        "final_minus_R1_omission": _ci(paired(fin_om, cell(comp, "R1", "omission")), meta),
        "false_rejection_final_minus_R0p": _ci(paired(fin_c, cell(comp, "R0p", "correct")), meta)}
    det, fr = out["detection_R6x_first"]["estimate"], out["false_rejection_R6x_first"]["estimate"]
    out["discrimination"] = {
        "R6x_first": None if det is None or fr is None else (1 - fr) - (1 - det),
        "R1_R0p": (1 - out["false_rejection_R0p"]["estimate"]) - (1 - out["detection_R1"]["estimate"]),
        "R6x_final": (1 - out["gated_final"]["false_rejection"]["estimate"])
        - (1 - out["gated_final"]["detection"]["estimate"])}
    # secondary: compliance of the first submission
    out["first_submission_compliance"] = {"all": _compliance(s),
                                          **{v: _compliance(g) for v, g in s.groupby("version")}}
    # gate counts (descriptive)
    gate = {}
    for v, g in s.groupby("version"):
        acc, fired = g[g.r6x_first_y == 0], g[g.r6x_gate_fired]
        gate[v] = dict(calls=len(g), first_accepts=len(acc), first_accept_compliant=int(acc.r6x_first_compliant.sum()),
                       first_rejects=int((g.r6x_first_y == 1).sum()),
                       first_reject_compliant=int(g[g.r6x_first_y == 1].r6x_first_compliant.sum()),
                       gate_fired=len(fired), retry_accept=int((fired.r6x_retry_y == 0).sum()),
                       retry_reject=int((fired.r6x_retry_y == 1).sum()),
                       gate_reject=int(((fired.r6x_final_y == 1) & (fired.r6x_retry_y != 1)).sum()))
    out["gate"] = gate
    # secondary: detection conditional on the removed sentence's label in the first submission
    om = s[s.version == "omission"].copy()
    removed = {i: json.loads((OMISSION_DIR / f"{i}.json").read_text()) for i in om.item_id.unique()}
    om["removed_label"] = [label_of(json.loads(js), removed[i]["removed_sentence"])
                           for js, i in zip(om.r6x_first_classification, om.item_id)]
    by = {}
    for k, g in om.groupby("removed_label"):
        g2 = g.dropna(subset=["r6x_first_y"])
        by[k] = dict(calls=len(g), first_rejects=int((g2.r6x_first_y == 1).sum()),
                     detection=float(g2.r6x_first_y.mean()) if len(g2) else None,
                     items=int(g.item_id.nunique()), trajectories=int(meta.loc[g.item_id.unique(), "cluster"].nunique()))
    out["detection_by_removed_sentence_label"] = {
        "note": "call level, omission versions, first submission and first verdict; label of the entry equal "
                "to the removed sentence (src.replay.r6x.label_of; 'not listed' if no such entry)",
        "pre_specified_group": "include", "by_label": by}
    rej = om[om.r6x_first_y == 1]
    hits = [right_reason(t, removed[i]["right_reason_markers"]) for t, i in zip(rej.first_reasoning_r6x, rej.item_id)]
    out["right_reason_deterministic_first"] = {"rejects": len(rej), "right_reason": int(sum(hits))}
    return out


def r6_correct_section(a08: pd.DataFrame, comp: pd.DataFrame, meta) -> dict:
    s = a08[(a08.variant == "R6") & (a08.version == "correct")]
    if s.empty:
        return {"status": "not run"}
    first, final = cell(s, "R6", "correct", "r6_first_y"), cell(s, "R6", "correct", "r6_final_y")
    r0p = cell(comp, "R0p", "correct")
    acc = s[s.r6_first_y == 0]
    fired = s[s.r6_gate_fired.fillna(False).astype(bool)]
    return {"label": "descriptive (D31: existing R6 on the correct versions of the 50 omission items)",
            "n_items": int(s.item_id.nunique()), "calls": len(s), "missing_first": int(s.r6_first_y.isna().sum()),
            "false_rejection_first": _ci(first, meta), "false_rejection_final": _ci(final, meta),
            "false_rejection_first_minus_R0p": _ci(paired(first, r0p), meta),
            "false_rejection_final_minus_R0p": _ci(paired(final, r0p), meta),
            "gate": dict(first_accepts=len(acc), first_accept_compliant=int(acc.r6_first_compliant.sum()),
                         gate_fired=len(fired), retry_accept=int((fired.r6_retry_y == 0).sum()),
                         retry_reject=int((fired.r6_retry_y == 1).sum()),
                         gate_reject=int(((fired.r6_final_y == 1) & (fired.r6_retry_y != 1)).sum()))}


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    a08 = load_a08()
    if a08.empty:
        return {"status": "not run"}
    meta = cluster_meta()
    comp = comparison_cells(main_calls.assign(check="MAIN"), load_stage("a06"))
    return {"label": "ADDENDUM (D30 R6x, D31 R6 correct versions; fixed before their own run; outside the Holm family)",
            "R6x": r6x_section(a08, comp, meta), "R6_correct": r6_correct_section(a08, comp, meta),
            "spend_usd_a08": float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                       if r.get("stage") == STAGE and r.get("mode") == "live"))}
